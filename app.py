#!/usr/bin/env python3
"""发票夹子 Web UI - Streamlit版本"""
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import yaml

st.set_page_config(page_title="发票夹子", page_icon="📎", layout="wide")

@st.cache_resource
def load_config():
    cfg = Path(__file__).parent / "config" / "config.yaml"
    if not cfg.exists():
        st.error(f"配置文件不存在: {cfg}")
        st.stop()
    with open(cfg) as f:
        return yaml.safe_load(f)

def get_db_path(cfg):
    return Path(cfg["storage"]["db_path"]).expanduser()

@st.cache_data(ttl=30)
def load_invoices(cfg, filters=None):
    from invoice_clipper.database import query_invoices
    return query_invoices(get_db_path(cfg), filters or {})

def sidebar_nav():
    st.sidebar.title("📎 发票夹子")
    st.sidebar.markdown("---")
    page = st.sidebar.radio("功能菜单",
        ["📤 扫描发票", "📋 发票列表", "🔍 查询筛选", "📥 导出报销"],
        label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.caption("v2.0 | 财务人员专用工具")
    return page

def page_scan(cfg):
    st.header("📤 扫描发票")
    st.markdown("上传PDF或图片文件，自动识别发票信息")
    files = st.file_uploader("拖拽文件到此处，或点击选择",
        type=["pdf", "png", "jpg", "jpeg", "bmp", "tiff", "ofd"],
        accept_multiple_files=True)
    if files:
        st.markdown("---")
        st.subheader("识别结果")
        from invoice_clipper.processor import InvoiceProcessor
        proc = InvoiceProcessor(cfg)
        results = []
        bar = st.progress(0)
        txt = st.empty()
        for idx, f in enumerate(files):
            bar.progress((idx + 1) / len(files))
            txt.text(f"正在处理: {f.name}")
            tmp = Path("/tmp") / f.name
            with open(tmp, "wb") as fp:
                fp.write(f.getvalue())
            r = proc.process_file(tmp, source="web")
            if r:
                results.append({"文件名": f.name, "状态": "✅ 成功",
                    "发票号码": r.get("invoice_number", "-"),
                    "日期": r.get("date", "-"),
                    "销售方": r.get("seller", "-"),
                    "金额": f"¥{r.get('amount_with_tax', 0):,.2f}"})
            else:
                results.append({"文件名": f.name, "状态": "❌ 失败",
                    "发票号码": "-", "日期": "-", "销售方": "-", "金额": "-"})
            if tmp.exists():
                tmp.unlink()
        bar.empty()
        txt.empty()
        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
            ok = sum(1 for r in results if r["状态"] == "✅ 成功")
            st.success(f"处理完成: {ok}/{len(results)} 张识别成功")

def page_list(cfg):
    st.header("📋 发票列表")
    invs = load_invoices(cfg, {"only_included": False})
    if not invs:
        st.info("暂无发票记录，请先扫描发票")
        return
    data = []
    for i in invs:
        data.append({"ID": i.get("id"), "日期": i.get("date", ""),
            "发票号码": i.get("invoice_number", ""), "销售方": i.get("seller", ""),
            "购买方": i.get("buyer", ""), "金额": i.get("amount_with_tax", 0),
            "状态": "❌ 排除" if i.get("excluded") else "✅ 正常"})
    df = pd.DataFrame(data)
    c1, c2, c3 = st.columns(3)
    c1.metric("总发票数", f"{len(df)} 张")
    c2.metric("可报销", f"{len(df[df['状态'] == '✅ 正常'])} 张")
    c3.metric("总金额", f"¥{df['金额'].sum():,.2f}")
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        filt = st.multiselect("状态筛选", ["✅ 正常", "❌ 排除"], default=["✅ 正常"])
    with c2:
        search = st.text_input("搜索销售方/购买方", placeholder="输入关键词...")
    fd = df.copy()
    if filt:
        fd = fd[fd["状态"].isin(filt)]
    if search:
        fd = fd[fd["销售方"].str.contains(search, case=False, na=False) |
                fd["购买方"].str.contains(search, case=False, na=False)]
    st.dataframe(fd.drop(columns=["ID"]), use_container_width=True, hide_index=True,
        column_config={"金额": st.column_config.NumberColumn(format="¥%.2f")})
    st.markdown("---")
    st.subheader("批量操作")
    ids = st.multiselect("选择发票ID", options=df["ID"].tolist(), format_func=lambda x: f"#{x}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚫 标记为排除", use_container_width=True) and ids:
            from invoice_clipper.database import update_invoice_status
            for i in ids:
                update_invoice_status(get_db_path(cfg), i, excluded=True)
            st.success(f"已排除 {len(ids)} 张发票")
            st.rerun()
    with c2:
        if st.button("✅ 恢复为正常", use_container_width=True) and ids:
            from invoice_clipper.database import update_invoice_status
            for i in ids:
                update_invoice_status(get_db_path(cfg), i, excluded=False)
            st.success(f"已恢复 {len(ids)} 张发票")
            st.rerun()

def page_query(cfg):
    st.header("🔍 查询筛选")
    st.markdown("按条件筛选发票，支持日期范围和关键词搜索")
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
    only = st.checkbox("只显示可报销发票", value=True)
    if st.button("🔍 查询", type="primary", use_container_width=True):
        filters = {"date_from": d1.strftime("%Y-%m-%d") if d1 else None,
            "date_to": d2.strftime("%Y-%m-%d") if d2 else None,
            "seller": seller if seller else None,
            "buyer": buyer if buyer else None,
            "only_included": only}
        invs = load_invoices(cfg, filters)
        if not invs:
            st.warning("没有找到符合条件的发票")
            return
        data = [{"日期": i.get("date", ""), "发票号码": i.get("invoice_number", ""),
            "销售方": i.get("seller", ""), "购买方": i.get("buyer", ""),
            "金额": i.get("amount_with_tax", 0),
            "状态": "❌ 排除" if i.get("excluded") else "✅ 正常"} for i in invs]
        df = pd.DataFrame(data)
        st.success(f"找到 {len(df)} 张发票，合计 ¥{df['金额'].sum():,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True,
            column_config={"金额": st.column_config.NumberColumn(format="¥%.2f")})

def page_export(cfg):
    st.header("📥 导出报销")
    st.markdown("选择筛选条件，一键导出Excel明细表和PDF报销包")
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
    filters = {"date_from": d1.strftime("%Y-%m-%d") if d1 else None,
        "date_to": d2.strftime("%Y-%m-%d") if d2 else None,
        "seller": seller if seller else None,
        "buyer": buyer if buyer else None,
        "only_included": True}
    invs = load_invoices(cfg, filters)
    if not invs:
        st.warning("没有符合条件的发票")
        return
    total = sum(i.get("amount_with_tax", 0) for i in invs)
    st.info(f"将导出 {len(invs)} 张发票，合计 ¥{total:,.2f}")
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
                st.download_button(label=f"下载 {name}", data=f.read(),
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
