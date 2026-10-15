import zipfile
from io import BytesIO

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from rembg import new_session, remove

st.set_page_config(
    page_title="SEIF PHOTO STUDIO",
    page_icon="📸",
    layout="wide",
)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');

:root {
    color-scheme: dark;
    --studio-bg: #101114;
    --studio-panel: #1B1D22;
    --studio-border: #343740;
    --studio-gold: #D4AF37;
    --studio-gold-hover: #E7C65A;
    --studio-text: #F5F5F5;
    --studio-muted: #B9BDC7;
}

/* خلفية ثابتة وواضحة */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: #101114 !important;
    color: #F5F5F5 !important;
    font-family: 'Cairo', sans-serif !important;
}

/* منع بهتان الشريط العلوي أثناء التمرير */
[data-testid="stHeader"] {
    background-color: #101114 !important;
    background-image: none !important;
    box-shadow: none !important;
}

/* القائمة الجانبية */
[data-testid="stSidebar"] {
    background: #181A1F !important;
    border-right: 1px solid #343740 !important;
}

[data-testid="stSidebar"] > div:first-child {
    background: #181A1F !important;
}

/* اتجاه النصوص */
.stApp {
    direction: rtl;
}

.stApp h1, .stApp h2, .stApp h3 {
    color: #D4AF37 !important;
    font-weight: 800 !important;
    text-align: right;
}

.stApp p, .stApp label,
.stApp [data-testid="stMarkdownContainer"] {
    color: #F5F5F5;
    text-align: right;
}

.stApp small,
.stApp .stCaption {
    color: #B9BDC7 !important;
}

/* العنوان الرئيسي */
.hero {
    text-align: center !important;
    padding: 24px 12px 30px;
    margin-bottom: 22px;
    background: #181A1F;
    border: 1px solid #343740;
    border-radius: 18px;
}

.hero h1 {
    color: #D4AF37 !important;
    text-align: center !important;
    margin-bottom: 8px;
    letter-spacing: .3px;
}

.hero p {
    color: #D0D2D8 !important;
    text-align: center !important;
    margin-top: 6px;
}

/* الحاويات والبطاقات */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpander"],
[data-testid="stFileUploader"] {
    border-color: #343740 !important;
}

[data-testid="stExpander"] {
    background: #181A1F !important;
    border-radius: 12px !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 1.5rem !important;
    max-width: 1500px;
}

/* الأزرار */
div.stButton > button,
div.stDownloadButton > button,
[data-testid="stLinkButton"] a {
    width: 100%;
    min-height: 46px;
    border-radius: 11px !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 700 !important;
    transition: background-color .15s ease, border-color .15s ease !important;
}

div.stButton > button[kind="primary"] {
    background: #D4AF37 !important;
    color: #111111 !important;
    border: 1px solid #D4AF37 !important;
}

div.stButton > button[kind="primary"]:hover {
    background: #E7C65A !important;
    border-color: #E7C65A !important;
}

div.stDownloadButton > button,
[data-testid="stLinkButton"] a {
    background: #24262D !important;
    color: #F5F5F5 !important;
    border: 1px solid #454954 !important;
}

div.stDownloadButton > button:hover,
[data-testid="stLinkButton"] a:hover {
    border-color: #D4AF37 !important;
    color: #E7C65A !important;
}

/* حقول الإدخال والقوائم */
.stApp input,
.stApp textarea,
.stApp [data-baseweb="select"] > div {
    background-color: #202228 !important;
    color: #F5F5F5 !important;
    border-color: #454954 !important;
}

/* أشرطة التمرير */
.stApp [data-testid="stMain"],
[data-testid="stSidebar"] > div {
    scrollbar-color: #454954 #101114;
}

/* لا نستخدم تعتيمًا أو فلاتر على محتوى التطبيق */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stSidebar"] {
    opacity: 1 !important;
    filter: none !important;
}

/* قسم التواصل */
.contact {
    text-align: center !important;
    padding: 24px 12px;
    border-top: 1px solid #343740;
    margin-top: 32px;
}

.contact h3,
.contact p {
    text-align: center !important;
}

@media (max-width: 768px) {
    [data-testid="stMainBlockContainer"] {
        padding: 1rem .8rem !important;
    }

    .hero {
        padding: 18px 10px 22px;
    }

    .hero h1 {
        font-size: 1.65rem;
    }
}
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
