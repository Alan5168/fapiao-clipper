"""
发票数据库模块 - SQLite 存储
"""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str):
    """初始化数据库表"""
    with get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT,
                invoice_code TEXT,
                date TEXT,
                amount REAL,
                amount_with_tax REAL,
                tax REAL,
                seller TEXT,
                buyer TEXT,
                category TEXT,
                invoice_type TEXT,
                source TEXT,
                original_filename TEXT,
                stored_path TEXT,
                excluded INTEGER DEFAULT 0,
                created_at TEXT,
                raw_text TEXT,
                raw_json TEXT,
                -- 验真与风控字段
                tax_status TEXT DEFAULT 'unchecked',   -- unchecked/normal/voided/red_flushed/lost/abnormal
                blacklist_status TEXT DEFAULT 'unchecked',  -- unchecked/clean/blacklisted/suspect
                ofd_signature_ok INTEGER,               -- 1=有效 0=无效 None=无需验证
                warnings TEXT DEFAULT '[]',            -- JSON: [{level, code, message}]
                verified_at TEXT,
                check_msg TEXT                         -- 查验平台返回的原始信息
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON invoices(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_seller ON invoices(seller)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_buyer ON invoices(buyer)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_status ON invoices(tax_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_excluded ON invoices(excluded)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoice_number ON invoices(invoice_number)")
        conn.commit()
    logger.info(f"数据库初始化完成: {db_path}")


def insert_invoice(db_path: str, data: dict) -> int:
    # 只插入预定义的列
    cols = [
        "invoice_number", "invoice_code", "date", "amount", "amount_with_tax", "tax",
        "seller", "buyer", "category", "invoice_type", "source", "original_filename",
        "stored_path", "created_at", "raw_text", "raw_json",
    ]
    placeholders = ",".join(":" + c for c in cols)
    with get_conn(db_path) as conn:
        cur = conn.execute(
            f"INSERT INTO invoices ({','.join(cols)}) VALUES ({placeholders})",
            {k: v for k, v in data.items() if k in cols}
        )
        conn.commit()
        return cur.lastrowid


def is_duplicate(db_path: str, invoice_number: str, amount_with_tax: float) -> bool:
    """判断是否重复（发票号+金额完全相同）"""
    if not invoice_number:
        return False
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM invoices WHERE invoice_number=? AND amount_with_tax=?",
            (invoice_number, amount_with_tax)
        ).fetchone()
    return row is not None


def exists_by_invoice_number(db_path: str, invoice_number: str) -> bool:
    """判断发票号码是否已存在（不管金额，防止同一发票多次入库）"""
    if not invoice_number:
        return False
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM invoices WHERE invoice_number=? LIMIT 1",
            (invoice_number,)
        ).fetchone()
    return row is not None


def query_invoices(db_path: str, filters: dict) -> List[dict]:
    """
    filters 支持：
      date_from, date_to: 日期范围 YYYY-MM-DD
      seller: 销售方（模糊匹配）
      buyer: 购买方（模糊匹配）
      exclude_ids: 排除的id列表
      only_included: 只返回未排除的（默认True）
      only_problem: 只返回有问题（warning）的
    """
    sql = "SELECT * FROM invoices WHERE 1=1"
    params = []

    if filters.get("date_from"):
        sql += " AND date >= ?"
        params.append(filters["date_from"])
    if filters.get("date_to"):
        sql += " AND date <= ?"
        params.append(filters["date_to"])
    if filters.get("seller"):
        sql += " AND seller LIKE ?"
        params.append(f"%{filters['seller']}%")
    if filters.get("buyer"):
        sql += " AND buyer LIKE ?"
        params.append(f"%{filters['buyer']}%")
    if filters.get("only_included", True):
        sql += " AND excluded = 0"
    if filters.get("exclude_ids"):
        placeholders = ",".join("?" * len(filters["exclude_ids"]))
        sql += f" AND id NOT IN ({placeholders})"
        params.extend(filters["exclude_ids"])

    sql += " ORDER BY date ASC, id ASC"

    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_invoice_status(db_path: str, inv_id: int, excluded: bool = True):
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE invoices SET excluded=? WHERE id=?",
            (1 if excluded else 0, inv_id)
        )
        conn.commit()


def update_verification_result(db_path: str, inv_id: int, result: dict):
    """更新验真结果"""
    with get_conn(db_path) as conn:
        conn.execute("""
            UPDATE invoices SET
                tax_status = :tax_status,
                blacklist_status = :blacklist_status,
                ofd_signature_ok = :ofd_signature_ok,
                warnings = :warnings,
                verified_at = :verified_at,
                check_msg = :check_msg
            WHERE id = :id
        """, {
            "id": inv_id,
            "tax_status": result.get("tax_status", "unchecked"),
            "blacklist_status": result.get("blacklist_status", "unchecked"),
            "ofd_signature_ok": result.get("ofd_signature_ok"),
            "warnings": json.dumps(result.get("warnings", []), ensure_ascii=False),
            "verified_at": datetime.now().isoformat(),
            "check_msg": result.get("check_msg", ""),
        })
        conn.commit()


def exclude_invoice(db_path: str, invoice_id: int, excluded: bool = True):
    """标记发票为排除/恢复"""
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE invoices SET excluded=? WHERE id=?",
            (1 if excluded else 0, invoice_id)
        )
        conn.commit()


def find_by_seller(db_path: str, seller: str) -> List[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE seller LIKE ? ORDER BY date ASC",
            (f"%{seller}%",)
        ).fetchall()
    return [dict(r) for r in rows]


def get_invoice_by_id(db_path: str, invoice_id: int) -> Optional[dict]:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    return dict(row) if row else None


def get_all_invoices(db_path: str) -> List[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM invoices ORDER BY date ASC").fetchall()
    return [dict(r) for r in rows]


def get_problem_invoices(db_path: str, filters: dict = None) -> List[dict]:
    """
    返回有问题的发票（warnings非空 或 tax_status异常 或 blacklist非clean）
    """
    filters = filters or {}
    filters["only_included"] = False  # 问题发票不管有没有 excluded
    sql = """
        SELECT * FROM invoices WHERE 1=1
        AND (
            warnings != '[]' AND warnings != '[]' AND warnings IS NOT NULL
            OR tax_status NOT IN ('unchecked', 'normal', '')
            OR blacklist_status NOT IN ('unchecked', 'clean', '')
        )
    """
    params = []
    if filters.get("date_from"):
        sql += " AND date >= ?"
        params.append(filters["date_from"])
    if filters.get("date_to"):
        sql += " AND date <= ?"
        params.append(filters["date_to"])
    sql += " ORDER BY date DESC"
    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
