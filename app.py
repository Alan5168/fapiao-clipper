#!/usr/bin/env python3
"""发票夹子 Web UI - Streamlit版本"""
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import yaml

st.set_page_config(page_title="发票夹子", page_icon="📎", layout="wide")

# ─────────────────────────────────────────────────────────
# 6 项风控检查说明（统一展示文案）
# ─────────────────────────────────────────────────────────
RISK_ITEMS = [
    ("内控禁止项",    "礼品/烟酒卡/奢侈品等",                            "BLOCK"),
    ("重复报销",      "发票号+金额已报销过",                             "BLOCK"),
    ("跨年检查",      "非本年发票自动排除",                              "WARN"),
    ("个人抬头发票",  "仅差旅/交通/通讯类reimbursable",                        "WARN"),
    ("违法失信主体",  "销售方在税务局失信名录中（用户自查）",            "BLOCK"),
    ("税务状态",      "作废/红冲/失控等状态不能报销（用户自查）",        "BLOCK"),
]

INVOICE_VERIFY_URL = "https://inv-veri.chinatax.gov.cn/index.html"
BLACKLIST_URL      = "https://www.chinatax.gov.cn/chinatax/c101249/n2020011502/index.html"


@st.cache_resource
def load_config():
    cfg = Path(__file__).parent / "config" / "config.yaml"
    if not cfg.exists():
        cfg = Path(__file__).parent / "config" / "config.yaml.example"
    if not cfg.exists():
        st.error("配置文件不存在，请先运行 setup_config.py")
        st.stop()
    with open(cfg) as f:
        return yaml.safe_load(f)

def get_db_path(cfg):
    return Path(cfg["storage"]["db_path"]).expanduser().resolve()

def get_invoice_count(cfg):
    """返回 (总数, reimbursable数, 不reimbursable数)"""
    invs = load_invoices(cfg, {"only_included": False})
    total = len(invs)
    reimbursable = sum(1 for i in invs if not i.get("excluded"))
    return total, reimbursable, total - reimbursable

@st.cache_data(ttl=30)
def load_invoices(cfg, filters=None):
    from invoice_clipper.database import query_invoices as _q
    return _q(str(get_db_path(cfg)), filters or {})

def sidebar_nav():
    st.sidebar.title("📎 发票夹子")
    st.sidebar.markdown("---")
    page = st.sidebar.radio("功能菜单",
        ["📤 扫描发票", "📋 发票列表", "🔍 查询筛选", "📥 导出报销"],
        label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption("v1.4.0 | 财务人员专用工具")
    return page

def _render_risk_badge(level: str, code: str, message: str):
    if level == "BLOCK":
        color = "🔴"
        bg    = "background:#fff5f5;padding:8px 12px;border-radius:6px;border-left:4px solid #e53;"
    elif level == "WARN":
        color = "🟡"
        bg    = "background:#fffbeb;padding:8px 12px;border-radius:6px;border-left:4px solid #d97706;"
    else:
        color = "⚪"
        bg    = "background:#f9fafb;padding:8px 12px;border-radius:6px;"
    st.markdown(f"<div style='{bg}'>{color} <b>{code}</b>：{message}</div>",
                unsafe_allow_html=True)

def _render_warnings(warnings: list):
    if not warnings:
        st.success("✅ 未发现风控问题")
        return
    for w in warnings:
        _render_risk_badge(w.get("level", "WARN"), w.get("code", "?"), w.get("message", ""))

def _render_external_buttons(invoice_number: str, invoice_code: str):
    """发票查验 + 违法失信主体查询 按钮"""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"**🔗 发票查验**（国家税务总局）\n"
            f"[点击打开发票查验平台]({INVOICE_VERIFY_URL})\n"
            f"发票号码：`{invoice_number}` / 发票代码：`{invoice_code}`",
            unsafe_allow_html=True)
    with col2:
        st.markdown(
            f"**🔗 违法失信主体查询**（国家税务总局）\n"
            f"[点击打开失信查询页面]({BLACKLIST_URL})",
            unsafe_allow_html=True)

def page_scan(cfg):
    st.header("📤 扫描发票")
    st.markdown("上传 PDF 或图片文件，自动识别发票信息并执行 6 项风控检查。")
    st.info("💡 **风控说明**：内控禁止项 · 重复报销 · 跨年检查 · 个人抬头发票 · 违法失信主体（自查） · 税务状态（自查）")

    # ── 外部查验入口 ────────────────────────────────────
    with st.expander("🔗 外部查验入口", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📄 发票查验平台**")
            st.markdown(f"[国家税务总局发票查验]({INVOICE_VERIFY_URL})")
            st.code(f"发票号码 + 发票代码 + 开票日期 + 金额", language="")
        with col2:
            st.markdown("**🚫 违法失信主体查询**")
            st.markdown(f"[国家税务总局失信查询]({BLACKLIST_URL})")

    files = st.file_uploader(
        "拖拽文件到此处，或点击选择",
        type=["pdf", "png", "jpg", "jpeg", "bmp", "tiff", "ofd"],
        accept_multiple_files=True)

    if not files:
        return

    st.markdown("---")
    st.subheader("识别结果")
    from invoice_clipper.processor import InvoiceProcessor
    proc = InvoiceProcessor(cfg)
    results = []
    bar = st.progress(0)
    status_text = st.empty()

    for idx, f in enumerate(files):
        bar.progress((idx + 1) / len(files))
        status_text.text(f"正在处理: {f.name}")
        tmp = Path("/tmp") / f.name
        with open(tmp, "wb") as fp:
            fp.write(f.getvalue())
        r = proc.process_file(tmp, source="web")
        if r:
            inv_id     = r.get("id", "?")
            inv_no     = r.get("invoice_number", "-")
            date       = r.get("date", "-")
            seller     = r.get("seller", "-")
            amount     = r.get("amount_with_tax", 0)
            tax_amount = r.get("tax", 0)
            warnings   = []
            try:
                import json as _json
                warnings = _json.loads(r.get("warnings_json", "[]"))
            except Exception:
                pass

            # 6项风控摘要
            risk_summary = []
            for code, (_, _, level) in zip(
                    ["BANNED_ITEM","DUPLICATE","OVERDUE","PERSONAL_RECEIPT","BLACKLISTED","TAX_STATUS"],
                    [w.get("code") for w in warnings]):
                risk_summary.append("🔴" if level == "BLOCK" else "🟡")

            results.append({
                "ID":          inv_id,
                "文件名":      f.name,
                "状态":        "✅ 成功",
                "发票号码":    inv_no,
                "日期":        date,
                "销售方":      seller,
                "金额":        f"¥{amount:,.2f}",
                "税额":        f"¥{tax_amount:,.2f}",
                "风控":        " ".join(risk_summary) if risk_summary else "✅",
                "warnings":    warnings,
            })
        else:
            results.append({
                "ID": "-", "文件名": f.name, "状态": "❌ 失败",
                "发票号码": "-", "日期": "-", "销售方": "-",
                "金额": "-", "税额": "-", "风控": "❌",
                "warnings": [],
            })
        if tmp.exists():
            tmp.unlink()

    bar.empty()
    status_text.empty()

    if not results:
        return

    # ── 展示结果（可展开详情）───────────────────────────
    for r in results:
        with st.expander(
            f"{r['状态']} | {r['文件名']} | {r['发票号码']} | {r['金额']}",
            expanded=(r["状态"] == "❌ 失败")):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("**基本信息**")
                st.write(f"ID：{r['ID']}")
                st.write(f"发票号码：`{r['发票号码']}`")
                st.write(f"日期：{r['日期']}")
                st.write(f"销售方：{r['销售方']}")
                st.write(f"金额：{r['金额']}（税额 {r['税额']}）")
            with col2:
                st.markdown("**6 项风控检查结果**")
                _render_warnings(r["warnings"])
                st.markdown("---")
                _render_external_buttons(r["发票号码"],
                    results[0].get("发票代码",""))

    ok = sum(1 for r in results if r["状态"] == "✅ 成功")
    st.success(f"处理完成：{ok}/{len(results)} 张识别成功")

def page_list(cfg):
    st.header("📋 发票列表")
    invs_all = load_invoices(cfg, {"only_included": False})
    if not invs_all:
        st.info("暂无发票记录，请先扫描发票")
        return

    invs_ok = [i for i in invs_all if not i.get("excluded")]
    invs_ex = [i for i in invs_all if i.get("excluded")]

    total_amount    = sum(i.get("amount_with_tax", 0) for i in invs_all)
    reimbursable_amount = sum(i.get("amount_with_tax", 0) for i in invs_ok)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总发票数", f"{len(invs_all)} 张")
    c2.metric("reimbursable", f"{len(invs_ok)} 张")
    c3.metric("已排除", f"{len(invs_ex)} 张")
    c4.metric("reimbursable_amount", f"¥{reimbursable_amount:,.2f}",
              delta=f"总金额 ¥{total_amount:,.2f}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        filt = st.multiselect("状态筛选", ["✅ 正常", "❌ 排除"],
                              default=["✅ 正常"], key="list_filt")
    with c2:
        search = st.text_input("搜索销售方 / 购买方", placeholder="输入关键词...", key="list_search")

    # 构建 DataFrame（显示金额 = 发票金额，非报销金额）
    data = []
    for i in invs_all:
        import json
        warnings = []
        try:
            warnings = json.loads(i.get("warnings") or "[]")
        except Exception:
            pass
        risk_icon = ""
        if warnings:
            levels = [w.get("level") for w in warnings]
            risk_icon = "🔴" if "BLOCK" in levels else "🟡"
        data.append({
            "ID":          i.get("id"),
            "日期":        i.get("date", ""),
            "发票号码":    i.get("invoice_number", ""),
            "销售方":      i.get("seller", ""),
            "购买方":      i.get("buyer", ""),
            "金额":        i.get("amount_with_tax", 0),
            "税额":        i.get("tax", 0),
            "状态":        "❌ 排除" if i.get("excluded") else "✅ 正常",
            "风险":        risk_icon,
        })

    df = pd.DataFrame(data)

    # 过滤
    fd = df.copy()
    if "✅ 正常" not in filt and "❌ 排除" not in filt:
        fd = fd.iloc[:0]
    elif len(filt) == 1:
        fd = fd[fd["状态"] == filt[0]]
    if search:
        fd = fd[
            fd["销售方"].str.contains(search, case=False, na=False) |
            fd["购买方"].str.contains(search, case=False, na=False)
        ]

    st.dataframe(
        fd.drop(columns=["ID"]),
        use_container_width=True, hide_index=True,
        column_config={
            "金额": st.column_config.NumberColumn(format="¥%.2f"),
            "税额": st.column_config.NumberColumn(format="¥%.2f"),
        })

    # ── 发票详情 ──────────────────────────────────────
    if not fd.empty:
        st.markdown("---")
        st.subheader("📄 发票详情")
        selected_id = st.selectbox(
            "选择发票 ID 查看详情",
            options=fd["ID"].tolist(),
            format_func=lambda x: f"#{x} - {fd[fd['ID']==x]['发票号码'].values[0]} - "
                                  f"¥{fd[fd['ID']==x]['金额'].values[0]:,.2f}",
            key="detail_select")
        if selected_id:
            inv = next((i for i in invs_all if i.get("id") == selected_id), None)
            if inv:
                _render_invoice_detail(inv)

    # ── 批量操作 ───────────────────────────────────────
    st.markdown("---")
    st.subheader("批量操作")
    c1, c2 = st.columns(2)
    with c1:
        ids = st.multiselect("选择发票 ID",
            options=df["ID"].tolist(),
            format_func=lambda x: f"#{x}",
            key="batch_ids")
    with c2:
        st.write("")  # spacer
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("🚫 标记为排除", use_container_width=True) and ids:
            from invoice_clipper.database import update_invoice_status
            for i in ids:
                update_invoice_status(str(get_db_path(cfg)), int(i), excluded=True)
            st.success(f"已排除 {len(ids)} 张发票")
            st.rerun()
    with cc2:
        if st.button("✅ 恢复为正常", use_container_width=True) and ids:
            from invoice_clipper.database import update_invoice_status
            for i in ids:
                update_invoice_status(str(get_db_path(cfg)), int(i), excluded=False)
            st.success(f"已恢复 {len(ids)} 张发票")
            st.rerun()

def _render_invoice_detail(inv: dict):
    """渲染单张发票详情"""
    inv_id   = inv.get("id", "?")
    inv_no   = inv.get("invoice_number", "-")
    amount   = inv.get("amount_with_tax", 0)
    inv_code = inv.get("invoice_code", "")
    date     = inv.get("date", "-")
    seller   = inv.get("seller", "-")
    buyer    = inv.get("buyer", "-")
    tax_amt  = inv.get("tax", 0)
    category = inv.get("category", "-")
    inv_type = inv.get("invoice_type", "-")

    import json
    warnings = []
    try:
        warnings = json.loads(inv.get("warnings") or "[]")
    except Exception:
        pass

    st.markdown(f"### #{inv_id} - {inv_no} - ¥{amount:,.2f}")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**基本信息**")
        st.write(f"发票号码：`{inv_no}`")
        st.write(f"发票代码：`{inv_code}`")
        st.write(f"日期：{date}")
        st.write(f"销售方：{seller}")
        st.write(f"购买方：{buyer}")
    with col2:
        st.markdown("**金额信息**")
        st.write(f"价税合计：**¥{amount:,.2f}**")
        st.write(f"税额：¥{tax_amt:,.2f}")
        st.write(f"不含税金额：¥{amount - tax_amt:,.2f}")
        st.write(f"类型：{inv_type}")
        st.write(f"分类：{category}")

    st.markdown("---")
    st.markdown("**6 项风控检查结果**")
    _render_warnings(warnings)

    st.markdown("---")
    _render_external_buttons(inv_no, inv_code)

    # 原始 JSON（可折叠）
    with st.expander("📦 原始数据（JSON）"):
        st.json(inv, expanded=False)

def page_query(cfg):
    st.header("🔍 查询筛选")
    c1, c2 = st.columns(2)
    with c1:
        d1 = st.date_input("开始日期", value=None)
    with c2:
        d2 = st.date_input("结束日期", value=None)
    c1, c2 = st.columns(2)
    with c1:
        seller = st.text_input("销售方名称", placeholder="输入销售方关键词...")
    with c2:
        buyer = st.text_input("购买方名称", placeholder="输入购买方关键词...")
    only = st.checkbox("只显示reimbursable发票", value=True, key="qry_only")

    if st.button("🔍 查询", type="primary", use_container_width=True):
        filters = {
            "date_from":      d1.strftime("%Y-%m-%d") if d1 else None,
            "date_to":        d2.strftime("%Y-%m-%d") if d2 else None,
            "seller":         seller if seller else None,
            "buyer":          buyer if buyer else None,
            "only_included":  only,
        }
        invs = load_invoices(cfg, filters)
        if not invs:
            st.warning("没有找到符合条件的发票")
            return

        data = [{
            "ID":         i.get("id"),
            "日期":       i.get("date", ""),
            "发票号码":   i.get("invoice_number", ""),
            "销售方":     i.get("seller", ""),
            "购买方":     i.get("buyer", ""),
            "金额":       i.get("amount_with_tax", 0),
            "状态":       "❌ 排除" if i.get("excluded") else "✅ 正常",
        } for i in invs]
        df = pd.DataFrame(data)
        st.success(f"找到 {len(df)} 张发票，reimbursable_total ¥{df[df['状态']=='✅ 正常']['金额'].sum():,.2f}")
        st.dataframe(df.drop(columns=["ID"]),
            use_container_width=True, hide_index=True,
            column_config={"金额": st.column_config.NumberColumn(format="¥%.2f")})

def page_export(cfg):
    st.header("📥 导出报销")
    st.markdown("选择筛选条件，一键导出 Excel 明细表和 PDF 报销包。")
    st.subheader("筛选条件")
    c1, c2 = st.columns(2)
    with c1:
        d1 = st.date_input("开始日期", value=None, key="efrom")
    with c2:
        d2 = st.date_input("结束日期", value=None, key="eto")
    c1, c2 = st.columns(2)
    with c1:
        seller = st.text_input("销售方名称", placeholder="可选", key="eseller")
    with c2:
        buyer = st.text_input("购买方名称", placeholder="可选", key="ebuyer")
    fmt = st.radio("导出格式", ["Excel + PDF", "仅 Excel", "仅 PDF"], horizontal=True)

    st.markdown("---")
    st.subheader("预览")
    filters = {
        "date_from":     d1.strftime("%Y-%m-%d") if d1 else None,
        "date_to":       d2.strftime("%Y-%m-%d") if d2 else None,
        "seller":        seller if seller else None,
        "buyer":         buyer if buyer else None,
        "only_included": True,
    }
    invs = load_invoices(cfg, filters)
    if not invs:
        st.warning("没有符合条件的发票")
        return
    total = sum(i.get("amount_with_tax", 0) for i in invs)
    st.info(f"将导出 {len(invs)} 张发票，reimbursable_total ¥{total:,.2f}")

    if st.button("📥 开始导出", type="primary", use_container_width=True):
        from invoice_clipper.exporter import export_excel, export_merged_pdf, build_export_label
        edir = Path.home() / "Documents" / "发票夹子" / "exports"
        edir.mkdir(parents=True, exist_ok=True)
        label = build_export_label(filters)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []
        if fmt in ["Excel + PDF", "仅 Excel"]:
            xlpath = edir / f"报销明细_{label}_{ts}.xlsx"
            export_excel(invs, xlpath)
            results.append(("Excel 明细表", xlpath))
        if fmt in ["Excel + PDF", "仅 PDF"]:
            pdfpath = edir / f"报销发票_{label}_{ts}.pdf"
            r = export_merged_pdf(invs, pdfpath)
            if r:
                results.append(("PDF 报销包", pdfpath))
        st.success("导出完成！")
        for name, path in results:
            with open(path, "rb") as f:
                st.download_button(
                    label=f"下载 {name}", data=f.read(),
                    file_name=path.name, mime="application/octet-stream",
                    use_container_width=True)

def main():
    cfg = load_config()
    page = sidebar_nav()
    if page == "📤 扫描发票":
        page_scan(cfg)
    elif page == "📋 发票列表":
        page_list(cfg)
    elif page == "🔍 查询筛选":
        page_query(cfg)
    elif page == "📥 导出报销":
        page_export(cfg)

if __name__ == "__main__":
    main()
