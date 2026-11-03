import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# =================================================================
# CAO CẤP: THIẾT LẬP MẬT KHẨU QUẢN TRỊ
# =================================================================
PASSWORD_ADMIN = "PGD18@2026"  # Bạn có thể sửa chữ trong ngoặc kép này để đổi mật khẩu

# --- CẤU HÌNH DATABASE ---
DB_NAME = "debt_tracker.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debtors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            total_debt REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debtor_id INTEGER,
            amount_paid REAL,
            payment_date TEXT,
            reference TEXT,
            FOREIGN KEY (debtor_id) REFERENCES debtors (id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_NAME)

# --- HÀM BÓC TÁCH ĐẶC THÙ CHO BẢNG KÊ KHO BẠC ---
def parse_kho_bac_excel(file):
    df = pd.read_excel(file, header=None)
    extracted_debtors = []
    current_name = None
    
    for index, row in df.iterrows():
        for cell_value in row:
            if pd.isna(cell_value):
                continue
            cell_str = str(cell_value).strip()
            
            if "Tên đơn vị:" in cell_str:
                current_name = cell_str.split("Tên đơn vị:")[-1].strip()
            elif "Tổng số tiền phải trả:" in cell_str and current_name:
                money_part = cell_str.split("Tổng số tiền phải trả:")[-1].strip()
                money_clean = money_part.lower().replace('đ', '').replace('.', '').replace(',', '').strip()
                
                if money_clean.isdigit():
                    extracted_debtors.append({
                        "Tên đơn vị": current_name,
                        "Tổng phí phát sinh (VND)": float(money_clean)
                    })
                    current_name = None
    return extracted_debtors

# --- GIAO DIỆN APP ---
st.set_page_config(page_title="KBNN Khu Vực XIV - PGD số 18", layout="wide")
st.title("🏦 App Theo Dõi Trả Phí Chuyển Tiền KBNN khu vực XIV - PGD số 18")

tab1, tab2, tab3 = st.tabs(["📊 Tổng quan & Báo cáo", "➕ Nạp bảng kê phí KBNN (Excel)", "💵 Cập nhật đơn vị nộp phí"])

# --- TAB 1: TỔNG QUAN & BÁO CÁO ---
with tab1:
    st.subheader("Tình hình thực hiện nghĩa vụ phí của các đơn vị")
    conn = get_connection()
    query = """
        SELECT d.id, d.name AS "Tên đơn vị", d.total_debt AS "Tổng phí phát sinh (VND)",
               COALESCE(SUM(p.amount_paid), 0) AS "Đã nộp (VND)",
               (d.total_debt - COALESCE(SUM(p.amount_paid), 0)) AS "Còn thiếu (VND)"
        FROM debtors d LEFT JOIN payments p ON d.id = p.debtor_id GROUP BY d.id
    """
    df_debtors = pd.read_sql_query(query, conn)

    if not df_debtors.empty:
        total_initial = df_debtors["Tổng phí phát sinh (VND)"].sum()
        total_paid = df_debtors["Đã nộp (VND)"].sum()
        total_remaining = df_debtors["Còn thiếu (VND)"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng phí phát sinh", f"{total_initial:,.0f} VND")
        col2.metric("Tổng phí đã thu hồi", f"{total_paid:,.0f} VND", delta=f"{total_paid:,.0f}")
        col3.metric("Tổng phí còn thiếu", f"{total_remaining:,.0f} VND", delta=f"-{total_paid:,.0f}")

        st.markdown("---")
        st.dataframe(df_debtors[["Tên đơn vị", "Tổng phí phát sinh (VND)", "Đã nộp (VND)", "Còn thiếu (VND)"]], use_container_width=True)

        st.subheader("📈 Biểu đồ tiến độ hoàn thành phí")
        df_melted = pd.melt(df_debtors, id_vars=["Tên đơn vị"], value_vars=["Đã nộp (VND)", "Còn thiếu (VND)"], var_name="Trạng thái", value_name="Số tiền")
        fig = px.bar(df_melted, x="Tên đơn vị", y="Số tiền", color="Trạng thái", barmode="stack", color_discrete_map={"Đã nộp (VND)": "#2ecc71", "Còn thiếu (VND)": "#e74c3c"})
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📜 Lịch sử các giao dịch đơn vị nộp tiền vào tài khoản")
        query_history = """
            SELECT p.payment_date AS "Ngày giao dịch", d.name AS "Đơn vị nộp", 
                   p.amount_paid AS "Số tiền nộp (VND)", p.reference AS "Mã giao dịch / Ghi chú"
            FROM payments p
            JOIN debtors d ON p.debtor_id = d.id
            ORDER BY p.id DESC
        """
        df_history = pd.read_sql_query(query_history, conn)
        if not df_history.empty:
            st.dataframe(df_history, use_container_width=True)
    else:
        st.info("Hiện tại chưa có dữ liệu. Vui lòng qua tab 'Nạp bảng kê phí KBNN (Excel)'.")
    conn.close()

# --- TAB 2: NẠP FILE EXCEL BẢNG KÊ & XÓA BẢO MẬT ---
with tab2:
    st.subheader("🛠️ Khu vực cấu hình nội bộ")
    with st.expander("🔑 BẤM ĐỂ MỞ TÍNH NĂNG XÓA TOÀN BỘ DỮ LIỆU (CẦN MẬT KHẨU)", expanded=False):
        st.warning("Hành động này sẽ xóa vĩnh viễn toàn bộ danh sách đơn vị, số tiền phí phát sinh và cả lịch sử nộp tiền.")
        input_password = st.text_input("1. Nhập mật khẩu quản trị:", type="password", key="del_pass")
        confirm_code = st.text_input("2. Xác nhận hành động (Gõ chính xác chữ: XUATPHATLAI):", key="del_code")
        
        if st.button("🔴 KÍCH HOẠT XÓA TOÀN BỘ DỮ LIỆU HỆ THỐNG", type="primary"):
            if input_password == PASSWORD_ADMIN:
                if confirm_code == "XUATPHATLAI":
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM payments")
                        cursor.execute("DELETE FROM debtors")
                        conn.commit()
                        conn.close()
                        st.success("🔥 Đã xóa sạch toàn bộ cơ sở dữ liệu thành công!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Có lỗi xảy ra: {e}")
                else:
                    st.error("Mã hành động chưa đúng. Vui lòng gõ chữ 'XUATPHATLAI' viết hoa không dấu.")
            else:
                st.error("❌ SAI MẬT KHẨU QUẢN TRỊ! Bạn không có quyền xóa dữ liệu này.")

    st.markdown("---")
    col_manual, col_excel = st.columns(2)
    
    with col_manual:
        st.subheader("Cách 1: Thêm thủ công từng đơn vị")
        with st.form("add_debtor_form", clear_on_submit=True):
            new_name = st.text_input("Tên đơn vị / Cơ quan:")
            initial_debt = st.number_input("Tổng số phí phát sinh (VND):", min_value=0.0, step=1000.0, format="%f")
            submit_debtor = st.form_submit_button("Lưu hồ sơ đơn vị")

            if submit_debtor:
                if new_name.strip() == "":
                    st.error("Vui lòng điền tên đơn vị!")
                else:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO debtors (name, total_debt) VALUES (?, ?)", (new_name.strip(), initial_debt))
                        conn.commit()
                        st.success(f"🎉 Đã thêm thành công: {new_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Tên đơn vị này đã tồn tại trên hệ thống!")
                    finally:
                        conn.close()

    with col_excel:
        st.subheader("Cách 2: Nhập tự động từ Bảng kê Kho bạc")
        uploaded_file = st.file_uploader("Kéo và thả file Excel bảng kê phí chuyển tiền vào đây", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            try:
                debtor_list = parse_kho_bac_excel(uploaded_file)
                if debtor_list:
                    df_preview = pd.DataFrame(debtor_list)
                    st.write("🔍 **Kết quả bóc tách dữ liệu tự động từ file:**")
                    st.dataframe(df_preview, use_container_width=True)
                    
                    if st.button("Xác nhận nạp toàn bộ danh sách đơn vị này vào hệ thống"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        for item in debtor_list:
                            try:
                                cursor.execute("INSERT INTO debtors (name, total_debt) VALUES (?, ?)", 
                                               (item["Tên đơn vị"], item["Tổng phí phát sinh (VND)"]))
                            except sqlite3.IntegrityError:
                                cursor.execute("UPDATE debtors SET total_debt = total_debt + ? WHERE name = ?", 
                                               (item["Tổng phí phát sinh (VND)"], item["Tên đơn vị"]))
                        conn.commit()
                        conn.close()
                        st.success("✅ Đã nạp và cập nhật thành công phí cho các đơn vị!")
                        st.rerun()
                else:
                    st.warning("Không tìm thấy dữ liệu dạng 'Tên đơn vị' và 'Tổng số tiền phải trả' trong file này.")
            except Exception as e:
                st.error(f"Có lỗi khi xử lý dữ liệu: {e}")

# --- TAB 3: CẬP NHẬT ĐƠN VỊ NỘP TIỀN (HOÀN CHỈNH) ---
with tab3:
    st.subheader("Ghi nhận đơn vị nộp tiền vào tài khoản")
    conn = get_connection()
    df_select = pd.read_sql_query("SELECT id, name FROM debtors", conn)
    conn.close()

    if not df_select.empty:
        debtor_options = {row["name"]: row["id"] for _, row in df_select.iterrows()}
        with st.form("add_payment_form", clear_on_submit=True):
            selected_debtor_name = st.selectbox("Chọn đơn vị nộp phí:", options=list(debtor_options.keys()))