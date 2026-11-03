import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# --- CẤU HÌNH DATABASE ---
DB_NAME = "debt_tracker.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Bảng quản lý người nợ
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS debtors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            total_debt REAL
        )
    """
    )
    # Bảng quản lý lịch sử trả nợ vào tài khoản
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debtor_id INTEGER,
            amount_paid REAL,
            payment_date TEXT,
            reference TEXT,
            FOREIGN KEY (debtor_id) REFERENCES debtors (id)
        )
    """
    )
    conn.commit()
    conn.close()


init_db()


def get_connection():
    return sqlite3.connect(DB_NAME)


# --- GIAO DIỆN APP (STREAMLIT) ---
st.set_page_config(page_title="App Theo Dõi Trả Nợ", layout="wide")
st.title("💰 App Theo Dõi Cập Nhật Tình Hình Trả Nợ")

# Tab chức năng
tab1, tab2, tab3 = st.tabs(
    ["📊 Tổng quan & Báo cáo", "➕ Thêm người nợ mới", "💵 Cập nhật trả nợ"]
)

# --- TAB 1: TỔNG QUAN & BÁO CÁO ---
with tab1:
    st.subheader("Tình hình dư nợ hiện tại")

    conn = get_connection()
    # Truy vấn tính toán số tiền đã trả và còn nợ
    query = """
        SELECT 
            d.id,
            d.name AS "Người nợ",
            d.total_debt AS "Nợ ban đầu (VND)",
            COALESCE(SUM(p.amount_paid), 0) AS "Đã trả (VND)",
            (d.total_debt - COALESCE(SUM(p.amount_paid), 0)) AS "Còn nợ (VND)"
        FROM debtors d
        LEFT JOIN payments p ON d.id = p.debtor_id
        GROUP BY d.id
    """
    df_debtors = pd.read_sql_query(query, conn)

    if not df_debtors.empty:
        # Hiển thị các chỉ số tổng quan ở trên cùng
        total_initial = df_debtors["Nợ ban đầu (VND)"].sum()
        total_paid = df_debtors["Đã trả (VND)"].sum()
        total_remaining = df_debtors["Còn nợ (VND)"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng nợ ban đầu", f"{total_initial:,.0f} VND")
        col2.metric("Tổng đã thu hồi", f"{total_paid:,.0f} VND", delta=f"{total_paid:,.0f}")
        col3.metric("Tổng nợ còn lại", f"{total_remaining:,.0f} VND", delta=f"-{total_paid:,.0f}")

        st.markdown("---")

        # Hiển thị bảng số liệu chi tiết
        st.dataframe(
            df_debtors[["Người nợ", "Nợ ban đầu (VND)", "Đã trả (VND)", "Còn nợ (VND)"]],
            use_container_width=True,
        )

        # Biểu đồ tiến độ trực quan
        st.subheader("📈 Biểu đồ tiến độ trả nợ")
        df_melted = pd.melt(
            df_debtors,
            id_vars=["Người nợ"],
            value_vars=["Đã trả (VND)", "Còn nợ (VND)"],
            var_name="Trạng thái",
            value_name="Số tiền",
        )
        fig = px.bar(
            df_melted,
            x="Người nợ",
            y="Số tiền",
            color="Trạng thái",
            title="Tỷ lệ Đã trả vs Còn nợ theo từng người",
            barmode="stack",
            color_discrete_map={
                "Đã trả (VND)": "#2ecc71",
                "Còn nợ (VND)": "#e74c3c",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

        # Hiển thị lịch sử giao dịch gần đây
        st.markdown("---")
        st.subheader("📜 Lịch sử các giao dịch trả nợ vào tài khoản")
        query_history = """
            SELECT p.payment_date AS "Ngày giao dịch", d.name AS "Người trả", 
                   p.amount_paid AS "Số tiền (VND)", p.reference AS "Ghi chú/Mã GD"
            FROM payments p
            JOIN debtors d ON p.debtor_id = d.id
            ORDER BY p.id DESC
        """
        df_history = pd.read_sql_query(query_history, conn)
        if not df_history.empty:
            st.dataframe(df_history, use_container_width=True)
        else:
            st.info("Chưa có giao dịch trả nợ nào được ghi nhận.")
    else:
        st.info("Hiện tại chưa có dữ liệu người nợ. Vui lòng qua tab 'Thêm người nợ mới'.")

    conn.close()

# --- TAB 2: THÊM NGƯỜI NỢ MỚI ---
with tab2:
    st.subheader("Tạo hồ sơ quản lý nợ mới")
    with st.form("add_debtor_form", clear_on_submit=True):
        new_name = st.text_input("Họ và tên người nợ:")
        initial_debt = st.number_input(
            "Tổng số nợ ban đầu (VND):", min_value=0.0, step=100000.0, format="%f"
        )
        submit_debtor = st.form_submit_button("Lưu hồ sơ")

        if submit_debtor:
            if new_name.strip() == "":
                st.error("Vui lòng điền tên người nợ!")
            else:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO debtors (name, total_debt) VALUES (?, ?)",
                        (new_name.strip(), initial_debt),
                    )
                    conn.commit()
                    st.success(f"🎉 Đã thêm thành công người nợ: {new_name}")
                except sqlite3.IntegrityError:
                    st.error("Tên người nợ này đã tồn tại trên hệ thống!")
                finally:
                    conn.close()

# --- TAB 3: CẬP NHẬT TRẢ NỢ ---
with tab3:
    st.subheader("Ghi nhận tiền nợ chuyển vào tài khoản")
    conn = get_connection()
    df_select = pd.read_sql_query("SELECT id, name FROM debtors", conn)
    conn.close()

    if not df_select.empty:
        # Tạo danh bạ lựa chọn người trả nored
        debtor_options = {row["name"]: row["id"] for _, row in df_select.iterrows()}

        with st.form("add_payment_form", clear_on_submit=True):
            selected_debtor_name = st.selectbox("Chọn người trả nợ:", options=list(debtor_options.keys()))
            amount_to_pay = st.number_input(
                "Số tiền chuyển khoản vào tài khoản (VND):",
                min_value=0.0,
                step=50000.0,
                format="%f",
            )
            pay_date = st.date_input("Ngày nhận được tiền:")
            ref_text = st.text_input(
                "Ghi chú (Ví dụ: 'Chuyển khoản Vietcombank', 'Mã GD 12345'):"
            )

            submit_payment = st.form_submit_button("Xác nhận cập nhật tài khoản")

            if submit_payment:
                if amount_to_pay <= 0:
                    st.error("Số tiền trả nợ phải lớn hơn 0 VND!")
                else:
                    debtor_id = debtor_options[selected_debtor_name]
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO payments (debtor_id, amount_paid, payment_date, reference)
                        VALUES (?, ?, ?, ?)
                    """,
                        (debtor_id, amount_to_pay, str(pay_date), ref_text.strip()),
                    )
                    conn.commit()
                    conn.close()
                    st.success(
                        f"✅ Đã cập nhật: +{amount_to_pay:,.0f} VND từ {selected_debtor_name} vào tài khoản!"
                    )
                    st.rerun()
    else:
        st.info("Bạn cần thêm ít nhất một người nợ ở Tab 2 trước khi cập nhật giao dịch.")