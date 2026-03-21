"""
发票验真与风控模块

检查范围：
1. 内控禁止项：礼品/烟酒卡/奢侈品/涂改/大头小尾等
2. 抬头校验：个人 vs 企业
3. 超期检查：默认>365天
4. 重复报销：数据库已有相同发票号+金额
5. 税务状态：查验平台接口（详见 tax_verify_online）
"""

import re
import json
import logging
import httpx
from datetime import datetime, date
from typing import Optional, List
from pathlib import Path
from .blacklist import is_blacklisted

logger = logging.getLogger(__name__)

# ============================================================
# 内控禁止报销关键词（大小写不敏感）
# ============================================================
BANNED_KEYWORDS = {
    # 礼品卡/购物卡类
    "礼品", "购物卡", "预付卡", "储值卡", "会员卡", "兑换卡",
    "蛋糕卡", "蟹卡", "粽子卡",
    # 烟酒类
    "烟", "烟草", "白酒", "红酒", "葡萄酒", "洋酒", "啤酒",
    "茅台", "五粮液", "泸州老窖", "洋河", "剑南春", "水井坊", "郎酒",
    # 奢侈品
    "奢侈品", "爱马仕", "LV", "GUCCI", "香奈儿", "迪奥", "普拉达",
    "卡地亚", "劳力士", "百达翡丽", "欧米茄", "劳斯莱斯",
    # 其他明确禁止
    "高尔夫", "美容", "SPA", "按摩", "足疗",
    "健身", "体检", "游乐", "门票",
}

# 个人抬头发票例外项目（允许报销的差旅/通讯场景）
PERSONAL_EXCEPTIONS = {
    "差旅", "交通", "住宿", "通讯", "手机费", "火车票", "机票",
    "滴滴", "高德", "地铁", "公交", "打车", "出租车",
    "出行", "过路", "过桥", "停车",
}

# 默认发票有效期（天）
DEFAULT_VALIDITY_DAYS = 365


# ============================================================
# 核心验真函数
# ============================================================

def verify_invoice(fields: dict, db_path: str = None,
                   validity_days: int = DEFAULT_VALIDITY_DAYS) -> dict:
    """
    对一张发票进行全方位风控检查。
    返回：{
        'warnings': [{level, code, message}],
        'tax_status': str,
        'blacklist_status': str,
        'ofd_signature_ok': bool|None,
        'check_msg': str,
    }
    """
    warnings: List[dict] = []

    seller = fields.get("seller", "") or ""
    buyer = fields.get("buyer", "") or ""
    invoice_number = fields.get("invoice_number", "") or ""
    invoice_type = fields.get("invoice_type", "") or ""
    amount = fields.get("amount_with_tax") or 0
    inv_date_str = fields.get("date", "") or ""
    category = fields.get("category", "") or ""

    # ── 1. 内控禁止项检查 ─────────────────────────────────
    text_full = f"{seller} {buyer} {category} {invoice_type}"
    text_lower = text_full.lower()
    for kw in BANNED_KEYWORDS:
        if kw.lower() in text_lower:
            warnings.append({
                "level": "BLOCK",
                "code": "BANNED_ITEM",
                "message": f"检测到禁止报销项目「{kw}」，无法报销（如已取得合法凭证可申请特批）",
            })
            break  # 找到一个禁止项就不再继续加同类警告

    # ── 2. 个人抬头发票检查 ──────────────────────────────
    if "个人" in buyer or not buyer or buyer in ("无", "—", "-"):
        exception_found = any(ex in text_full for ex in PERSONAL_EXCEPTIONS)
        if not exception_found and warnings and warnings[-1]["code"] != "BANNED_ITEM":
            warnings.append({
                "level": "WARN",
                "code": "PERSONAL_RECEIPT",
                "message": f"个人抬头发票（购买方：{buyer}），仅差旅/交通/通讯类可报销，请确认是否符合报销规定",
            })

    # ── 3. 抬头错误检查 ──────────────────────────────────
    # 常见错误：简写、错字、括号不匹配
    if buyer and len(buyer) > 3:
        wrong_patterns = [
            (r"股份有公司", "股份有公司（请核对该字）"),
            (r"股份 限", "股份 限（可能有空格）"),
            (r"（?)有限公司", ""),  # just flag it
        ]
        for pat, suggestion in wrong_patterns:
            if re.search(pat, buyer):
                warnings.append({
                    "level": "WARN",
                    "code": "WRONG_TITLE",
                    "message": f"购买方抬头疑似有误：「{buyer}」，请核对后报销",
                })
                break

    # ── 4. 超期检查 ──────────────────────────────────────
    if inv_date_str:
        try:
            inv_date = datetime.strptime(inv_date_str[:10], "%Y-%m-%d").date()
            age_days = (date.today() - inv_date).days
            if age_days > validity_days:
                warnings.append({
                    "level": "BLOCK",
                    "code": "OVERDUE",
                    "message": f"发票已超期 {age_days} 天（规定≤{validity_days}天），无法报销（如有特殊情况请附说明）",
                })
        except ValueError:
            pass  # 日期格式不对就不检查

    # ── 5. 重复报销检查 ─────────────────────────────────
    if db_path and invoice_number and amount:
        from .database import is_duplicate as _check_dup
        if _check_dup(db_path, invoice_number, float(amount)):
            warnings.append({
                "level": "BLOCK",
                "code": "DUPLICATE",
                "message": f"发票号码 {invoice_number} 已报销过（相同号码+金额），疑似重复报销",
            })

    # ── 5b. 失信主体黑名单检查 ─────────────────────────
    if db_path:
        seller_tax_id = fields.get("seller_tax_id")
        bl_hit = is_blacklisted(db_path, seller_tax_id, seller)
        if bl_hit:
            violation = bl_hit.get("violation_type", "失信")
            warnings.append({
                "level": "BLOCK",
                "code": "BLACKLISTED",
                "message": f"销售方「{seller}」在{bl_hit.get('source', '黑名单')}失信名录中（{violation}），禁止报销",
            })

    # ── 6. 大头小尾检查 ─────────────────────────────────
    # 通过机器学习/规则判断票面金额是否异常（太小的金额可能是大头小尾）
    # 这里用启发式：金额极小（<1元）但有税额 → 疑似异常
    tax_amount = fields.get("tax") or 0
    if amount and amount < 1 and tax_amount and tax_amount > 0:
        warnings.append({
            "level": "WARN",
            "code": "SUSPICIOUS_AMOUNT",
            "message": f"票面金额异常（{amount}元），请确认非大头小尾发票",
        })

    # ── 7. OFD 电子签名验签 ─────────────────────────────
    ofd_ok = _verify_ofd_signature(fields.get("stored_path"))

    # ── 8. 税务查验（可选，有接口才执行）────────────────
    tax_status, blacklist_status, check_msg = _tax_bureau_check(
        invoice_number, fields.get("invoice_code"), fields.get("date"), fields.get("amount_with_tax")
    )
    if tax_status != "unchecked":
        status_labels = {
            "normal": "正常",
            "voided": "作废",
            "red_flushed": "红冲",
            "lost": "失控",
            "abnormal": "异常",
        }
        label = status_labels.get(tax_status, tax_status)
        if tax_status != "normal":
            warnings.append({
                "level": "BLOCK",
                "code": f"TAX_{tax_status.upper()}",
                "message": f"税务系统查验：发票状态为「{label}」，不能报销",
            })

    return {
        "warnings": warnings,
        "tax_status": tax_status,
        "blacklist_status": blacklist_status,
        "ofd_signature_ok": ofd_ok,
        "check_msg": check_msg,
    }


def _verify_ofd_signature(stored_path: str) -> Optional[bool]:
    """
    验证 OFD 电子签名（可选，有 easyofd 库才执行）
    返回：True=有效 / False=无效 / None=无需验证
    """
    if not stored_path:
        return None
    path = Path(stored_path)
    if path.suffix.lower() != ".ofd":
        return None
    try:
        from easyofd import OFDReader
        reader = OFDReader(path)
        # easyofd 可验证电子签章，返回 True/False
        is_valid = reader.verify_signature() if hasattr(reader, "verify_signature") else None
        logger.info(f"OFD 签名验证结果: {is_valid} — {path.name}")
        return is_valid
    except ImportError:
        logger.debug("easyofd 未安装，跳过 OFD 签名验证")
        return None
    except Exception as e:
        logger.warning(f"OFD 签名验证失败: {e}")
        return False


def _tax_bureau_check(invoice_number: str, invoice_code: str,
                      inv_date: str, amount: float) -> tuple:
    """
    调用税务查验接口（国家税务总局查验平台）

    目前支持：
    - 巨总税平台（fpcy.jss.com.cn）- 需要 cookie 登录，较难自动化
    - 企业内部白名单（可配置 in config）

    返回：(tax_status, blacklist_status, check_msg)
    如无法查验返回 ('unchecked', 'unchecked', '')
    """
    if not invoice_number or not invoice_code:
        return "unchecked", "unchecked", ""

    # 检查是否有配置内部黑名单（公司自建白名单/黑名单）
    # 可在 config.yaml 中配置 blacklist_companies: [...]
    # 此处留接口，后续接入
    try:
        # 留空接口，供后续接入企业黑名单数据库或税局 API
        return "unchecked", "unchecked", ""
    except Exception:
        return "unchecked", "unchecked", ""


def classify_invoice_type(seller: str, buyer: str, category: str, invoice_type: str) -> str:
    """
    智能分类发票类型，用于判断是否属于特殊报销场景
    返回：餐饮/交通/住宿/办公/差旅/个人/其他
    """
    text = f"{seller} {buyer} {category}".lower()
    if any(k in text for k in ["餐饮", "饭店", "餐厅", "酒店", "宾馆"]):
        return "餐饮住宿"
    if any(k in text for k in ["航空", "铁路", "火车", "机票", "滴滴", "打车", "交通"]):
        return "交通出行"
    if any(k in text for k in ["办公", "文具", "打印", "复印", "耗材"]):
        return "办公用品"
    if any(k in text for k in ["咨询", "服务", "代理", "顾问", "设计"]):
        return "服务费"
    if any(k in text for k in ["培训", "教育", "课程"]):
        return "培训费"
    return "其他"


# ============================================================
# CLI 批量验真命令
# ============================================================

def verify_all_pending(db_path: str, cfg: dict = None) -> dict:
    """
    对数据库中所有未验真的发票执行批量验真
    """
    from .database import get_all_invoices, update_verification_result

    invoices = get_all_invoices(db_path)
    results = {"clean": 0, "warning": 0, "blocked": 0, "errors": 0}
    validity_days = (cfg or {}).get("validity_days", DEFAULT_VALIDITY_DAYS)

    for inv in invoices:
        if inv.get("tax_status") not in ("unchecked", None, ""):
            continue  # 已验真过，跳过
        try:
            result = verify_invoice(inv, db_path, validity_days)
            update_verification_result(db_path, inv["id"], result)
            levels = [w["level"] for w in result["warnings"]]
            if "BLOCK" in levels:
                results["blocked"] += 1
            elif levels:
                results["warning"] += 1
            else:
                results["clean"] += 1
        except Exception as e:
            logger.error(f"验真失败 #{inv['id']}: {e}")
            results["errors"] += 1

    return results
