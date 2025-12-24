import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import re
import os

def reshape_arabic(text):
    return get_display(arabic_reshaper.reshape(str(text)))

VALID_USERNAME = "romany"
VALID_PASSWORD = "1122"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول")
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        login = st.form_submit_button("دخول")
        if login:
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                st.success("✅ تم تسجيل الدخول بنجاح")
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

st.set_page_config(page_title="صيدلية د/روماني", layout="centered")
st.title(" صيدلية د/ روماني عاطف يوسف")

uploaded_file = st.file_uploader("📤 ارفع ملف PDF يحتوي على جدول", type=["pdf"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"

    # استخراج اسم العميل والتاريخ
    client_name = ""
    dispensed_date = ""

    for line in full_text.split("\n"):
        if "Name" in line:
            match = re.search(r"Name\s*:\s*([^\n/]+)", line)
            if match:
                client_name = match.group(1).strip()
        if "Transaction Date" in line:
            match = re.search(r"Transaction Date\s*:\s*(\d{2}/\d{2}/\d{4})", line)
            if match:
                dispensed_date = match.group(1)

    # ✅ استخراج الدواء والكمية والسعر من الأسطر المحددة
    lines = full_text.split("\n")
    med_list = []
    seen_numbers = set()

    for i in range(len(lines) - 1):
        combined_line = lines[i].strip() + " " + lines[i + 1].strip()

        match_number = re.search(r"(\d+)-\s", combined_line)
        if not match_number:
            continue

        num = match_number.group(1)
        if num in seen_numbers:
            continue
        seen_numbers.add(num)

        # استخراج اسم الدواء
        match = re.search(r"\d-\s(.*?)(/|\s/\s|\s/\S)", combined_line)
        if match:
            med_name = match.group(1).strip()
        else:
            match_alt = re.search(r"\d-\s(.*?)(\d+\s|EGP|Box|time|ml|MG)", combined_line)
            if match_alt:
                med_name = match_alt.group(1).strip()
            else:
                match_basic = re.search(r"\d-\s(.*)", combined_line)
                if match_basic:
                    med_name = match_basic.group(1).strip()
                else:
                    continue

        qty_match = re.search(r"EGP\s+\d+\.\d+\s+(\d+)", combined_line)
        price_match = re.search(r"(\d+\.\d+)\s+(Box|Strip|Amp|Sach|Film|Vial|Tab|Sachets|sachets|Cart)", combined_line, re.IGNORECASE)

        qty = float(qty_match.group(1)) if qty_match else 0.0
        unit_price = float(price_match.group(1)) if price_match else 0.0
        total_price = round(qty * unit_price, 2)

        # ✅ استبعاد الدواء إذا كانت الكمية = 0
        if qty > 0:
            med_list.append({
                "اسم الصنف": med_name,
                "الكمية": qty,
                "سعر الوحدة": unit_price,
                "سعر الكمية": total_price
            })

    # 🟩 عرض النتائج
    if med_list:
        df = pd.DataFrame(med_list)
        st.subheader("📋 جدول الأدوية المستخرجة (قابل للتعديل):")
        edited_df = st.data_editor(
            df,
            column_config={
                "اسم الصنف": st.column_config.TextColumn("اسم الصنف"),
                "الكمية": st.column_config.NumberColumn("الكمية"),
                "سعر الوحدة": st.column_config.NumberColumn("سعر الوحدة"),
                "سعر الكمية": st.column_config.NumberColumn("سعر الكمية"),
            },
            num_rows="fixed",
            use_container_width=True
        )

        # ✅ إعادة حساب "سعر الكمية" تلقائيًا بعد التعديل
        edited_df["سعر الكمية"] = edited_df["الكمية"] * edited_df["سعر الوحدة"]

        # زر تحميل Excel
        output = BytesIO()
        edited_df.to_excel(output, index=False)
        output.seek(0)
        st.download_button(
            label="⬇️ تحميل Excel",
            data=output,
            file_name="approved_meds.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # توليد PDF
        if st.button("📄 توليد إيصال PDF"):
            class PDF(FPDF):
                def header(self):
                    pdf.add_font("Amiri", "", "Amiri-Regular.ttf", uni=True)
                    self.add_font("Amiri", "B", "Amiri-Bold.ttf", uni=True)
                    self.set_fill_color(230, 230, 230)
                    self.image("logo.png", x=10, y=8, w=20)
                    self.set_font("Amiri", "B", 14)
                    self.cell(0, 10, reshape_arabic("صيدلية د/ روماني عاطف يوسف"), ln=1, align="C")
                    self.set_font("Amiri", "", 11)
                    self.cell(0, 10, reshape_arabic("م.ض: 01-40-181-00591-5"), ln=1, align="C")
                    self.cell(0, 10, reshape_arabic("س.ت: 94294"), ln=1, align="C")
                    self.set_font("Amiri", "", 10)
                    self.cell(0, 10, reshape_arabic("العنوان: اسيوط - الفتح - عزبه التحرير - شارع رقم ١"), ln=1, align="C")
                    self.cell(0, 10, reshape_arabic("تليفون: 01557000365"), ln=1, align="C")
                    self.ln(5)

                def footer(self):
                    self.set_y(-20)
                    self.set_font("Amiri", "", 10)
                    self.set_text_color(100)
                    self.cell(0, 10, reshape_arabic("شكراً لتعاملكم معنا ❤"), ln=1, align="C")
                    self.cell(0, 10, reshape_arabic(f"صفحة رقم {self.page_no()}"), align="C")

            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Amiri", "", 11)

            pdf.cell(0, 10, reshape_arabic(client_name) + reshape_arabic("اسم العميل: "), ln=1, align="R")
            pdf.cell(0, 10, reshape_arabic("التاريخ: " + dispensed_date), ln=1, align="R")
            pdf.ln(5)

            headers = ["اسم الصنف", "الكمية", "سعر الوحدة", "سعر الكمية"]
            col_widths = [80, 25, 30, 35]
            row_height = 10
            row_count = 0
            rows_per_page = 25

            def draw_table_header():
                pdf.set_fill_color(230, 230, 230)
                pdf.set_font("Amiri", "B", 12)
                for i, h in enumerate(headers):
                    pdf.cell(col_widths[i], row_height, reshape_arabic(h), border=1, align="C", fill=True)
                pdf.ln()

            draw_table_header()

            for index, row in edited_df.iterrows():
                if row_count >= rows_per_page:
                    pdf.add_page()
                    draw_table_header()
                    row_count = 0

                pdf.cell(col_widths[0], row_height, reshape_arabic(str(row["اسم الصنف"])), border=1, align="C")
                pdf.cell(col_widths[1], row_height, reshape_arabic(str(row["الكمية"])), border=1, align="C")
                pdf.cell(col_widths[2], row_height, reshape_arabic(str(row["سعر الوحدة"])), border=1, align="C")
                pdf.cell(col_widths[3], row_height, reshape_arabic(str(row["سعر الكمية"])), border=1, align="C")
                pdf.ln()
                row_count += 1

            pdf.ln(5)
            pdf.cell(0, 10, reshape_arabic(f"عدد الأصناف: {len(edited_df)}"), ln=1, align="R")
            pdf.cell(0, 10, reshape_arabic(f"الإجمالي: {edited_df['سعر الكمية'].sum():.2f} EGP"), ln=1, align="R")

            pdf_output = pdf.output(dest='S')
            if isinstance(pdf_output, str):
                pdf_output = pdf_output.encode('latin-1')
            pdf_buffer = BytesIO(pdf_output)


            base_name = os.path.splitext(uploaded_file.name)[0]
            output_name = f"{base_name}_receipt.pdf"

            st.download_button(
                label="⬇️ تحميل إيصال PDF",
                data=pdf_buffer,
                file_name=output_name,
                mime="application/pdf"
            )
    else:
        st.info("ℹ️ لم يتم التعرف على أي أصناف حتى الآن.")



