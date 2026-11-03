import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

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
    """
    Hàm quét qua file Excel để tự động gom nhóm Tên đơn vị và Tổng số tiền phải trả
    tương ứng từ các bảng kê liên tiếp nhau.
    """
    # Đọc toàn bộ các hàng dưới dạng chuỗi để quét tự do, không phụ thuộc tên cột
    df = pd.read_excel(file, header=None)
    
    extracted_debtors = []
    current_name = None
    
    # Duyệt qua từng ô dữ liệu để tìm kiếm từ khóa
    for index, row in df.iterrows():
        for cell_value in row:
            if pd.isna(cell_value):
                continue
            
            cell_str = str(cell_value).strip()
            
            # 1. Tìm tên đơn vị
            if "Tên đơn vị:" in cell_str:
                # Lấy phần tên đứng sau dấu hai chấm
                current_name = cell_str.split("Tên đơn vị:")[-1].strip()
                
            # 2. Tìm tổng số tiền phải trả tương ứng liền sau tên đơn vị đó
            elif "Tổng số tiền phải trả:" in cell_str and current_name:
                money_part = cell_str.split("Tổng số tiền phải trả:")[-1].strip()
                # Làm sạch chuỗi tiền: xóa chữ 'đ', loại bỏ dấu chấm/phẩy phân tách hàng nghìn
                money_clean = money_part.lower().replace('đ', '').replace('.', '').replace(',', '').strip()
                
                if money_clean.isdigit():
                    extracted_debtors.append({
                        "Họ và tên người nợ": current_name,
                        "Tổng số nợ ban đầu (VND)": float(money_clean)
                    })
                    # Reset lại biến sau khi đã ghép cặp thành công
                    current_name = None
                    
    return extracted_debtors

# --- GIAO DIỆN APP (STREAMLIT) ---
st.set_page_config(page_title="App Theo Dõi Trả Nợ", layout="wide")
st.title("💰 App Theo Dõi Cập Nhật Tình Hình Trả Nợ")

tab1, tab2, tab3 = st.tabs(["📊 Tổng quan & Báo cáo", "➕ Thêm người nợ (Từng người / File Excel)", "💵 Cập nhật trả nợ"])

# --- TAB 1: TỔNG QUAN & BÁO CÁO ---
with tab1:
    st.subheader("Tình hình dư nợ hiện tại")
    conn = get_connection()
    query = """
        SELECT d.id, d.name AS "Người nợ", d.total_debt AS "Nợ ban đầu (VND)",
               COALESCE(SUM(p.amount_paid), 0) AS "Đã trả (VND)",
               (d.total_debt - COALESCE(SUM(p.amount_paid), 0)) AS "Còn nợ (VND)"
        FROM debtors d LEFT JOIN payments p ON d.id = p.debtor_id GROUP BY d.id
    """
    df_debtors = pd.read_sql_query(query, conn)

    if not df_debtors.empty:
        total_initial = df_debtors["Nợ ban đầu (VND)"].sum()
        total_paid = df_debtors["Đã trả (VND)"].sum()
        total_remaining = df_debtors["Còn nợ (VND)"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng nợ ban đầu", f"{total_initial:,.0f} VND")
        col2.metric("Tổng đã thu hồi", f"{total_paid:,.0f} VND", delta=f"{total_paid:,.0f}")
        col3.metric("Tổng nợ còn lại", f"{total_remaining:,.0f} VND", delta=f"-{total_paid:,.0f}")

        st.markdown("---")
        st.dataframe(df_debtors[["Người nợ", "Nợ ban đầu (VND)", "Đã trả (VND)", "Còn nợ (VND)"]], use_container_width=True)

        st.subheader("📈 Biểu đồ tiến độ trả nợ")
        df_melted = pd.melt(df_debtors, id_vars=["Người nợ"], value_vars=["Đã trả (VND)", "Còn nợ (VND)"], var_name="Trạng thái", value_name="Số tiền")
        fig = px.bar(df_melted, x="Người nợ", y="Số tiền", color="Trạng thái", barmode="stack", color_discrete_map={"Đã trả (VND)": "#2ecc71", "Còn nợ (VND)": "#e74c3c"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Hiện tại chưa có dữ liệu người nợ. Vui lòng qua tab 'Thêm người nợ'.")
    conn.close()

# --- TAB 2: THÊM NGƯỜI NỢ (BÓC TÁCH TỰ ĐỘNG BẢNG KÊ) ---
with tab2:
    col_manual, col_excel = st.columns(2)
    
    with col_manual:
        st.subheader("Cách 1: Thêm thủ công từng người")
        with st.form("add_debtor_form", clear_on_submit=True):
            new_name = st.text_input("Họ và tên người nợ:")
            initial_debt = st.number_input("Tổng số nợ ban đầu (VND):", min_value=0.0, step=1000.0, format="%f")
            submit_debtor = st.form_submit_button("Lưu hồ sơ")

            if submit_debtor:
                if new_name.strip() == "":
                    st.error("Vui lòng điền tên người nợ!")
                else:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO debtors (name, total_debt) VALUES (?, ?)", (new_name.strip(), initial_debt))
                        conn.commit()
                        st.success(f"🎉 Đã thêm thành công: {new_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Tên người nợ này đã tồn tại!")
                    finally:
                        conn.close()

    with col_excel:
        st.subheader("Cách 2: Nhập tự động từ Bảng kê Kho bạc")
        uploaded_file = st.file_uploader("Kéo và thả file Excel bảng kê phí chuyển tiền vào đây", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            try:
                # Gọi hàm bóc tách dữ liệu thông minh
                debtor_list = parse_kho_bac_excel(uploaded_file)
                
                if debtor_list:
                    df_preview = pd.DataFrame(debtor_list)
                    st.write("🔍 **Kết quả bóc tách dữ liệu tự động từ file của bạn:**")
                    st.dataframe(df_preview, use_container_width=True)
                    
                    if st.button("Xác nhận nạp toàn bộ danh sách này vào hệ thống"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        success_count = 0
                        skip_count = 0
                        
                        for item in debtor_list:
                            try:
                                cursor.execute("INSERT INTO debtors (name, total_debt) VALUES (?, ?)", 
                                               (item["Họ và tên người nợ"], item["Tổng số nợ ban đầu (VND)"]))
                                success_count += 1
                            except sqlite3.IntegrityError:
                                # Nếu trùng tên, tiến hành cộng dồn số nợ mới vào số nợ cũ luôn
                                cursor.execute("UPDATE debtors SET total_debt = total_debt + ? WHERE name = ?", 
                                               (item["Tổng số nợ ban đầu (VND)"], item["Họ và tên người nợ"]))
                                success_count += 1
                                
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Đã nạp thành công dữ liệu công nợ vào hệ thống!")
                        st.rerun()
                else:
                    st.warning("Không tìm thấy dữ liệu dạng 'Tên đơn vị' và 'Tổng số tiền phải trả' trong file này.")
                    
            except Exception as e:
                st.error(f"Có lỗi khi xử lý dữ liệu: {e}")

# --- TAB 3: CẬP NHẬT TRẢ NỢ ---
with tab3:
    st.subheader("Ghi nhận tiền nợ chuyển vào tài khoản")
    conn = get_connection()
    df_select = pd.read_sql_query("SELECT id, name FROM debtors", conn)
    conn.close()

    if not df_select.empty:
        debtor_options = {row["name"]: row["id"] for _, row in df_select.iterrows()}
        with st.form("add_payment_form", clear_on_submit=True):
            selected_debtor_name = st.selectbox("Chọn người trả nợ:", options=list(debtor_options.keys()))
            amount_to_pay = st.number_input("Số tiền chuyển khoản vào tài khoản (VND):", min_value=0.0, step=50000.0, format="%f")
            pay_date = st.date_input("Ngày nhận được tiền:")
            ref_text = st.text_input("Ghi chú (Ví dụ: 'Chuyển khoản tài khoản MB', 'Mã GD 9987'):")
            submit_payment = st.form_submit_button("Xác nhận cập nhật tài khoản")

            if submit_payment:
                if amount_to_pay <= 0:
                    st.error("Số tiền phải lớn hơn 0 VND!")
                else:
                    debtor_id = debtor_options[selected_debtor_name]
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO payments (debtor_id, amount_paid, payment_date, reference) VALUES (?, ?, ?, ?)",
                                   (debtor_id, amount_to_pay, str(pay_date), ref_text.strip()))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Đã cập nhật: +{amount_to_pay:,.0f} VND từ {selected_debtor_name}")
                    st.rerun()