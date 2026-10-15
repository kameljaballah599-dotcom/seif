
st.markdown("""
<style>
/* ألوان ثابتة للتطبيق بالكامل */
:root {
    color-scheme: dark;
    --studio-bg: #101114;
    --studio-panel: #1B1D22;
    --studio-border: #343740;
    --studio-gold: #D4AF37;
    --studio-text: #F5F5F5;
    --studio-muted: #C1C4CC;
}

/* خلفية ثابتة أثناء التمرير */
html,
body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.stApp {
    background: #101114 !important;
    color: #F5F5F5 !important;
}

/* منع تغيّر لون الشريط العلوي */
[data-testid="stHeader"] {
    background: #101114 !important;
    color: #F5F5F5 !important;
    box-shadow: none !important;
}

/* القائمة الجانبية */
[data-testid="stSidebar"] {
    background: #181A1F !important;
    border-right: 1px solid #343740 !important;
}

[data-testid="stSidebar"] * {
    color: #F5F5F5;
}

/* مساحة المحتوى */
[data-testid="stMainBlockContainer"] {
    background: transparent !important;
    padding-top: 1.5rem !important;
}

/* البطاقات والأقسام */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpander"],
[data-testid="stFileUploader"] {
    border-color: #343740 !important;
}

/* النصوص */
.stApp p,
.stApp label,
.stApp [data-testid="stMarkdownContainer"] {
    color: #F5F5F5;
}

.stApp small,
.stApp .stCaption {
    color: #C1C4CC !important;
}

/* العناوين الذهبية */
h1, h2, h3 {
    color: #D4AF37 !important;
}

/* الأزرار */
.stButton > button,
.stDownloadButton > button {
    background: #D4AF37 !important;
    color: #111111 !important;
    border: 1px solid #D4AF37 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    opacity: 1 !important;
    transition: background-color 0.15s ease !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    background: #E5C65B !important;
    color: #111111 !important;
    border-color: #E5C65B !important;
}

/* حقول الإدخال */
.stApp input,
.stApp textarea,
.stApp [data-baseweb="select"] > div {
    background-color: #202228 !important;
    color: #F5F5F5 !important;
    border-color: #454954 !important;
}

/* لا تسمح بتعتيم الواجهة أثناء التمرير */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stSidebar"],
[data-testid="stHeader"] {
    opacity: 1 !important;
    filter: none !important;
}

/* تحديد المساحة من دون تغيير ألوان الخلفية */
.block-container {
    max-width: 1400px;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}

/* شريط التمرير */
::-webkit-scrollbar {
    width: 10px;
}

::-webkit-scrollbar-track {
    background: #101114;
}

::-webkit-scrollbar-thumb {
    background: #454954;
    border-radius: 8px;
}

::-webkit-scrollbar-thumb:hover {
    background: #D4AF37;
}
</style>
""", unsafe_allow_html=True)
