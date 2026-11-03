import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date
from io import BytesIO
import re

# ==================================================
# CẤU HÌNH
# ==================================================

PASSWORD_ADMIN = "PGD18@2026"

DB_NAME = "debt_tracker.db"

# ==================================================
# DATABASE
# ==================================================

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debtors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            total_debt REAL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debtor_id INTEGER,
            amount_paid REAL,
            payment_date TEXT,
            reference TEXT,
            FOREIGN KEY (debtor_id)
            REFERENCES debtors(id)
            ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_payment_debtor
        ON payments(debtor_id)
    """)

    conn.commit()
    conn.close()


init_db()

# ==================================================
# HÀM ĐỌC FILE EXCEL KBNN
# ==================================================

def parse_kho_bac_excel(file):

    df = pd.read_excel(file, header=None)

    extracted = []

    current_name = None

    for _, row in df.iterrows():

        for cell in row:

            if pd.isna(cell):
                continue

            text = str(cell).strip()

            if "Tên đơn vị:" in text:
                current_name = text.split("Tên đơn vị:")[-1].strip()

            elif "Tổng số tiền phải trả:" in text and current_name:

                money_text = text.split(
                    "Tổng số tiền phải trả:"
                )[-1]

                amount = re.sub(r"[^\d]", "", money_text)

                if amount:

                    extracted.append({
                        "Tên đơn vị": current_name,
                        "Tổng phí phát sinh (VND)": float(amount)
                    })

                    current_name = None

    return extracted


# ==================================================
# GIAO DIỆN
# ==================================================

st.set_page_config(
    page_title="KBNN Khu vực XIV - PGD số 18",
    layout="wide"
)

st.title(
    "🏦 App Theo Dõi Phí Chuyển Tiền KBNN khu vực XIV - PGD số 18"
)

tab1, tab2, tab3 = st.tabs([
    "📊 Tổng quan",
    "📥 Nạp dữ liệu",
    "💵 Cập nhật nộp phí"
])

# ==================================================
# TAB 1
# ==================================================

with tab1:

    conn = get_connection()

    query = """
    SELECT
        d.id,
        d.name AS 'Tên đơn vị',
        d.total_debt AS 'Tổng phí phát sinh (VND)',
        COALESCE(SUM(p.amount_paid),0) AS 'Đã nộp (VND)',
        CASE
            WHEN (d.total_debt -
                COALESCE(SUM(p.amount_paid),0)) < 0
            THEN 0
            ELSE (
                d.total_debt -
                COALESCE(SUM(p.amount_paid),0)
            )
        END AS 'Còn thiếu (VND)'
    FROM debtors d
    LEFT JOIN payments p
    ON d.id = p.debtor_id
    GROUP BY d.id
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    st.subheader("Tổng hợp tình hình thực hiện")

    if not df.empty:

        total_fee = df["Tổng phí phát sinh (VND)"].sum()
        total_paid = df["Đã nộp (VND)"].sum()
        total_remain = df["Còn thiếu (VND)"].sum()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Tổng phí phát sinh",
            f"{total_fee:,.0f} VND"
        )

        col2.metric(
            "Đã thu hồi",
            f"{total_paid:,.0f} VND"
        )

        col3.metric(
            "Còn thiếu",
            f"{total_remain:,.0f} VND"
        )

        st.markdown("---")

        st.dataframe(
            df,
            use_container_width=True
        )

        # Biểu đồ

        chart_df = pd.melt(
            df,
            id_vars=["Tên đơn vị"],
            value_vars=[
                "Đã nộp (VND)",
                "Còn thiếu (VND)"
            ],
            var_name="Trạng thái",
            value_name="Số tiền"
        )

        fig = px.bar(
            chart_df,
            x="Tên đơn vị",
            y="Số tiền",
            color="Trạng thái",
            barmode="stack"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        # Xuất Excel

        output = BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                index=False,
                sheet_name="Bao Cao"
            )

        st.download_button(
            "📥 Xuất báo cáo Excel",
            data=output.getvalue(),
            file_name="BaoCaoPhiKBNN.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Chưa có dữ liệu.")

    # Lịch sử giao dịch

    conn = get_connection()

    history_sql = """
    SELECT
        p.payment_date AS 'Ngày giao dịch',
        d.name AS 'Đơn vị',
        p.amount_paid AS 'Số tiền nộp',
        p.reference AS 'Ghi chú'
    FROM payments p
    JOIN debtors d
    ON d.id = p.debtor_id
    ORDER BY p.id DESC
    """

    history = pd.read_sql_query(history_sql, conn)

    conn.close()

    st.markdown("---")
    st.subheader("📜 Lịch sử giao dịch")

    if not history.empty:
        st.dataframe(
            history,
            use_container_width=True
        )

# ==================================================
# TAB 2
# ==================================================

with tab2:

    st.subheader("Thêm đơn vị")

    col1, col2 = st.columns(2)

    # thêm thủ công

    with col1:

        with st.form(
            "add_debtor",
            clear_on_submit=True
        ):

            name = st.text_input(
                "Tên đơn vị"
            )

            debt = st.number_input(
                "Tổng phí phát sinh",
                min_value=0.0,
                step=1000.0
            )

            submit = st.form_submit_button(
                "Lưu"
            )

            if submit:

                try:

                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute("""
                    INSERT INTO debtors(
                        name,
                        total_debt
                    )
                    VALUES (?,?)
                    """, (name, debt))

                    conn.commit()
                    conn.close()

                    st.success(
                        "Đã thêm đơn vị."
                    )

                    st.rerun()

                except sqlite3.IntegrityError:
                    st.error(
                        "Tên đơn vị đã tồn tại."
                    )

    # import excel

    with col2:

        uploaded_file = st.file_uploader(
            "Nạp file Excel",
            type=["xlsx", "xls"]
        )

        if uploaded_file:

            data = parse_kho_bac_excel(
                uploaded_file
            )

            if data:

                preview = pd.DataFrame(data)

                st.dataframe(preview)

                if st.button(
                    "Xác nhận nhập dữ liệu"
                ):

                    conn = get_connection()
                    cursor = conn.cursor()

                    for item in data:

                        try:

                            cursor.execute("""
                            INSERT INTO debtors(
                                name,
                                total_debt
                            )
                            VALUES (?,?)
                            """, (
                                item["Tên đơn vị"],
                                item["Tổng phí phát sinh (VND)"]
                            ))

                        except sqlite3.IntegrityError:

                            cursor.execute("""
                            UPDATE debtors
                            SET total_debt=
                            total_debt + ?
                            WHERE name=?
                            """, (
                                item["Tổng phí phát sinh (VND)"],
                                item["Tên đơn vị"]
                            ))

                    conn.commit()
                    conn.close()

                    st.success(
                        "Đã nhập dữ liệu thành công."
                    )

                    st.rerun()

    st.markdown("---")

    with st.expander(
        "🔐 Quản trị hệ thống"
    ):

        password = st.text_input(
            "Mật khẩu",
            type="password"
        )

        confirm = st.text_input(
            "Nhập: XUATPHATLAI"
        )

        if st.button(
            "Xóa toàn bộ dữ liệu"
        ):

            if password != PASSWORD_ADMIN:
                st.error("Sai mật khẩu.")

            elif confirm != "XUATPHATLAI":
                st.error("Sai mã xác nhận.")

            else:

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM payments"
                )

                cursor.execute(
                    "DELETE FROM debtors"
                )

                conn.commit()
                conn.close()

                st.success(
                    "Đã xóa toàn bộ dữ liệu."
                )

                st.rerun()

# ==================================================
# TAB 3
# ==================================================

with tab3:

    conn = get_connection()

    debt_query = """
    SELECT
        d.id,
        d.name,
        (
            d.total_debt -
            COALESCE(SUM(p.amount_paid),0)
        ) AS remaining
    FROM debtors d
    LEFT JOIN payments p
    ON d.id=p.debtor_id
    GROUP BY d.id
    """

    debtors = pd.read_sql_query(
        debt_query,
        conn
    )

    conn.close()

    if debtors.empty:

        st.warning(
            "Chưa có danh sách đơn vị."
        )

    else:

        debtor_map = {
            row["name"]:
            (
                row["id"],
                max(0, row["remaining"])
            )
            for _, row
            in debtors.iterrows()
        }

        selected = st.selectbox(
            "Chọn đơn vị",
            list(debtor_map.keys())
        )

        debtor_id, remaining = debtor_map[
            selected
        ]

        st.info(
            f"Còn phải nộp: {remaining:,.0f} VND"
        )

        amount = st.number_input(
            "Số tiền nộp",
            min_value=0.0,
            max_value=float(remaining)
            if remaining > 0
            else 0.0,
            step=1000.0
        )

        payment_date = st.date_input(
            "Ngày nộp",
            value=date.today()
        )

        reference = st.text_input(
            "Mã giao dịch / Ghi chú"
        )

        if st.button(
            "💾 Lưu giao dịch"
        ):

            if amount <= 0:

                st.error(
                    "Nhập số tiền hợp lệ."
                )

            elif amount > remaining:

                st.error(
                    "Số tiền vượt công nợ còn lại."
                )

            else:

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                INSERT INTO payments(
                    debtor_id,
                    amount_paid,
                    payment_date,
                    reference
                )
                VALUES (?,?,?,?)
                """,
                (
                    debtor_id,
                    amount,
                    payment_date.strftime("%Y-%m-%d"),
                    reference
                ))

                conn.commit()
                conn.close()

                st.success(
                    "Đã ghi nhận giao dịch."
                )

                st.rerun()