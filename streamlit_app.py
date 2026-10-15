
import io
import streamlit as st
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from rembg import remove, new_session

st.set_page_config(
    page_title="SEIF PHOTO STUDIO",
    page_icon="📸",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background-color: #111111; color: white; }
h1, h2, h3 { color: #d4af37 !important; }
.stButton button, .stDownloadButton button {
    border-radius: 10px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

st.title("📸 SEIF PHOTO STUDIO")
st.subheader("Professional Photo Background Studio")
st.write(
    "غيّر خلفية صورك، حضّر الصور الرسمية، "
    "وحافظ على ملامح الشخص وملابسه قدر الإمكان."
)

@st.cache_resource
def load_model():
    return new_session("u2net")

def remove_photo_background(image):
    session = load_model()
    result = remove(image.convert("RGBA"), session=session)
    if isinstance(result, bytes):
        result = Image.open(io.BytesIO(result))
    return result.convert("RGBA")

def make_background(size, mode, color, uploaded_bg=None):
    if mode == "صورة خلفية مخصصة" and uploaded_bg is not None:
        bg = uploaded_bg.convert("RGB")
        return ImageOps.fit(bg, size, method=Image.Resampling.LANCZOS).convert("RGBA")

    if mode == "رمادي":
        color = "#808080"
    elif mode == "أبيض":
        color = "#FFFFFF"
    elif mode == "أسود":
        color = "#000000"

    bg = Image.new("RGBA", size, color)
    return bg

def compose_photo(foreground, background):
    foreground = foreground.convert("RGBA")
    background = background.convert("RGBA")
    if foreground.size != background.size:
        background = background.resize(
            foreground.size, Image.Resampling.LANCZOS
        )
    return Image.alpha_composite(background, foreground)

def improve_photo(image, brightness, contrast, sharpness):
    result = image.convert("RGB")
    result = ImageEnhance.Brightness(result).enhance(brightness)
    result = ImageEnhance.Contrast(result).enhance(contrast)
    result = ImageEnhance.Sharpness(result).enhance(sharpness)
    return result

with st.sidebar:
    st.header("⚙️ إعدادات الصورة")

    background_mode = st.selectbox(
        "اختر الخلفية",
        ["رمادي", "أبيض", "أسود", "لون مخصص", "صورة خلفية مخصصة"]
    )

    custom_color = "#808080"
    if background_mode == "لون مخصص":
        custom_color = st.color_picker(
            "اختر لون الخلفية", "#808080"
        )

    background_upload = None
    if background_mode == "صورة خلفية مخصصة":
        background_file = st.file_uploader(
            "ارفع صورة الخلفية",
            type=["png", "jpg", "jpeg", "webp"],
            key="background"
        )
        if background_file:
            background_upload = Image.open(background_file).convert("RGB")

    st.divider()
    st.subheader("✨ تحسين خفيف للصورة")

    brightness = st.slider("الإضاءة", 0.7, 1.4, 1.0, 0.05)
    contrast = st.slider("التباين", 0.7, 1.4, 1.0, 0.05)
    sharpness = st.slider("الوضوح", 0.7, 1.5, 1.0, 0.05)

    st.caption(
        "هذه الإعدادات تعدّل الصورة العامة، "
        "ولا تضمن تنقيح الوجه وحده."
    )

uploaded_file = st.file_uploader(
    "📤 ارفع صورتك",
    type=["jpg", "jpeg", "png", "webp"]
)

if uploaded_file:
    original = Image.open(uploaded_file).convert("RGB")

    st.markdown("### الصورة الأصلية")
    st.image(original, use_container_width=True)

    process_button = st.button(
        "✂️ إزالة الخلفية وتعديل الصورة",
        type="primary",
        use_container_width=True
    )

    if process_button:
        if (
            background_mode == "صورة خلفية مخصصة"
            and background_upload is None
        ):
            st.error("ارفع صورة الخلفية أولًا.")
        else:
            try:
                with st.spinner(
                    "جارٍ قصّ الشخص وإزالة الخلفية... "
                    "قد تستغرق العملية وقتًا في أول استخدام."
                ):
                    cutout = remove_photo_background(original)

                    if background_mode == "لون مخصص":
                        bg_color = custom_color
                    else:
                        bg_color = "#808080"

                    background = make_background(
                        cutout.size,
                        background_mode,
                        bg_color,
                        background_upload
                    )

                    final_image = compose_photo(cutout, background)
                    final_image = improve_photo(
                        final_image,
                        brightness,
                        contrast,
                        sharpness
                    )

                    st.session_state["original_result"] = original
                    st.session_state["final_result"] = final_image

            except Exception as e:
                st.error(
                    "حدث خطأ أثناء معالجة الصورة. "
                    "تأكد من اتصال الإنترنت ثم أعد المحاولة."
                )
                st.caption(str(e))

if "final_result" in st.session_state:
    st.divider()
    st.markdown("## 🖼️ مقارنة قبل وبعد")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**قبل التعديل**")
        st.image(
            st.session_state["original_result"],
            use_container_width=True
        )

    with col2:
        st.markdown("**بعد التعديل**")
        st.image(
            st.session_state["final_result"],
            use_container_width=True
        )

    output = io.BytesIO()
    st.session_state["final_result"].save(
        output, format="PNG"
    )

    st.download_button(
        "⬇️ تحميل الصورة النهائية",
        data=output.getvalue(),
        file_name="SEIF_PHOTO_STUDIO.png",
        mime="image/png",
        use_container_width=True
    )

st.divider()
st.markdown("### 📍 معلومات الاستوديو")

st.link_button(
    "📍 موقع الاستوديو على Google Maps",
    "https://www.google.com/maps/search/?api=1&query=VG9M%2BPVX%2C+Rue+Taher+Sfar%2C+Kal%C3%A2a+Kebira"
)

st.write("📞 الهاتف: 97262953")
st.caption(
    "SEIF PHOTO STUDIO — Photo editing and background removal"
)
