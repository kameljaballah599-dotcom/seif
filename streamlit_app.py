
import io
from pathlib import Path

import streamlit as st
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from rembg import new_session, remove


# =========================================================
# SEIF PHOTO STUDIO PRO
# =========================================================

APP_DIR = Path(__file__).resolve().parent
BG_DIR = APP_DIR / "backgrounds"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

CATEGORIES = {
    "رمادية": ("gray", 10),
    "بيضاء": ("white", 10),
    "أعراس": ("wedding", 20),
    "تقليدية تونسية وعربية": ("traditional", 15),
    "فاخرة وفنية": ("luxury", 15),
    "طبيعية": ("nature", 10),
}

SOLID_BACKGROUNDS = {
    "رمادي رسمي": "#B8B8B8",
    "أبيض": "#FFFFFF",
    "رمادي فاتح": "#E2E2E2",
    "أزرق هادئ": "#7797B5",
    "بيج": "#E7D7BE",
    "أسود": "#202020",
}

st.set_page_config(
    page_title="SEIF PHOTO STUDIO PRO",
    page_icon="📸",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
    }

    .stApp {
        background: #101114;
        color: #F5F5F5;
    }

    h1, h2, h3 {
        color: #D8B56D;
    }

    .studio-footer {
        margin-top: 35px;
        padding: 22px;
        border: 1px solid #9C7B3C;
        border-radius: 14px;
        text-align: center;
        background: #191A1F;
    }

    .small-note {
        color: #BBBBBB;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# AI BACKGROUND REMOVAL
# =========================================================

@st.cache_resource(show_spinner="جاري تجهيز نموذج الذكاء الاصطناعي...")
def load_rembg_session():
    return new_session("u2net_human_seg")


def open_uploaded_image(uploaded_file):
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def remove_background(image):
    session = load_rembg_session()

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    result = remove(
        buffer.getvalue(),
        session=session,
        alpha_matting=False,
    )

    return Image.open(io.BytesIO(result)).convert("RGBA")


# =========================================================
# BACKGROUND LIBRARY
# =========================================================

def get_backgrounds(folder_name):
    folder = BG_DIR / folder_name

    if not folder.exists():
        return []

    return sorted(
        [
            path for path in folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=lambda path: path.name.lower(),
    )


def get_all_background_count():
    return sum(
        len(get_backgrounds(folder))
        for folder, _ in CATEGORIES.values()
    )


def load_background(path, size):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        return ImageOps.fit(
            image,
            size,
            method=Image.Resampling.LANCZOS,
        )


def hex_to_rgb(hex_color):
    value = hex_color.lstrip("#")
    return tuple(
        int(value[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def create_solid_background(size, color):
    return Image.new("RGB", size, hex_to_rgb(color))


def create_gradient_background(size):
    width, height = size

    top = np.array([235, 235, 235], dtype=np.float32)
    bottom = np.array([135, 135, 135], dtype=np.float32)

    ratio = np.linspace(0, 1, height)[:, None, None]
    rows = top[None, None, :] * (1 - ratio)
    rows += bottom[None, None, :] * ratio

    array = np.repeat(rows, width, axis=1)
    array = np.clip(array, 0, 255).astype(np.uint8)

    return Image.fromarray(array, mode="RGB")


# =========================================================
# SUBJECT POSITIONING AND COMPOSITING
# =========================================================

def crop_subject_with_padding(subject):
    alpha = subject.getchannel("A")
    bbox = alpha.getbbox()

    if bbox is None:
        return subject

    left, top, right, bottom = bbox
    width, height = subject.size

    pad_x = max(8, int((right - left) * 0.04))
    pad_y = max(8, int((bottom - top) * 0.025))

    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(width, right + pad_x)
    bottom = min(height, bottom + pad_y)

    return subject.crop((left, top, right, bottom))


def compose_subject(
    subject,
    background,
    subject_width_percent=75,
    vertical_position=92,
    brightness=1.0,
    contrast=1.0,
):
    background = background.convert("RGB")
    subject = subject.convert("RGBA")

    canvas_width, canvas_height = background.size

    # Remove transparent margins without trimming the visible person.
    subject = crop_subject_with_padding(subject)

    target_width = int(
        canvas_width * subject_width_percent / 100
    )

    scale = min(
        target_width / max(1, subject.width),
        canvas_height * 0.96 / max(1, subject.height),
    )

    new_width = max(1, int(subject.width * scale))
    new_height = max(1, int(subject.height * scale))

    subject = subject.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )

    rgb = subject.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)

    subject.putdata([
        (*pixel, alpha)
        for pixel, alpha in zip(
            list(rgb.getdata()),
            list(subject.getchannel("A").getdata()),
        )
    ])

    x = (canvas_width - new_width) // 2

    # 0 = near top, 100 = near bottom.
    available_y = max(0, canvas_height - new_height)
    y = int(available_y * vertical_position / 100)

    result = background.copy().convert("RGBA")
    result.alpha_composite(subject, (x, y))

    return result.convert("RGB")


# =========================================================
# EXPORT
# =========================================================

def image_to_jpeg_bytes(image, quality=95):
    output = io.BytesIO()
    image.convert("RGB").save(
        output,
        format="JPEG",
        quality=quality,
        optimize=True,
    )
    return output.getvalue()


def image_to_png_bytes(image):
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


# =========================================================
# HEADER
# =========================================================

st.title("📸 SEIF PHOTO STUDIO PRO")
st.caption(
    "قصّ الشخص بالذكاء الاصطناعي • تغيير الخلفيات • "
    "الصور الرسمية • معاينة وتنزيل"
)

with st.sidebar:
    st.header("⚙️ إعدادات الصورة")

    uploaded_file = st.file_uploader(
        "ارفع صورة الشخص",
        type=["jpg", "jpeg", "png", "webp"],
    )

    st.divider()
    st.subheader("حجم الشخص ومكانه")

    subject_width = st.slider(
        "عرض الشخص بالنسبة إلى الصورة",
        min_value=30,
        max_value=100,
        value=75,
        step=5,
    )

    vertical_position = st.slider(
        "الموضع العمودي",
        min_value=0,
        max_value=100,
        value=92,
        help="0 أعلى الصورة، و100 أسفل الصورة.",
    )

    st.divider()
    st.subheader("تحسينات خفيفة")

    brightness = st.slider(
        "سطوع الشخص",
        min_value=0.70,
        max_value=1.30,
        value=1.0,
        step=0.05,
    )

    contrast = st.slider(
        "تباين الشخص",
        min_value=0.70,
        max_value=1.30,
        value=1.0,
        step=0.05,
    )


# =========================================================
# BACKGROUND SELECTION
# =========================================================

st.subheader("🖼️ مكتبة الخلفيات")

total_backgrounds = get_all_background_count()
st.write(f"الخلفيات الموجودة فعليًا: **{total_backgrounds} / 80**")

category_label = st.selectbox(
    "اختر فئة الخلفية",
    list(CATEGORIES.keys()),
)

folder_name, expected_count = CATEGORIES[category_label]
background_files = get_backgrounds(folder_name)

st.caption(
    f"الفئة: {category_label} — "
    f"الموجود: {len(background_files)} من {expected_count}"
)

background_mode = st.radio(
    "طريقة اختيار الخلفية",
    ["مكتبة الصور", "لون رسمي", "تدرّج رمادي"],
    horizontal=True,
)

selected_background_path = None
selected_solid_color = None

if background_mode == "مكتبة الصور":
    if background_files:
        selected_background_path = st.selectbox(
            "اختر خلفية",
            background_files,
            format_func=lambda path: path.name,
        )

        preview_columns = st.columns(4)

        for index, path in enumerate(background_files):
            with preview_columns[index % 4]:
                try:
                    with Image.open(path) as image:
                        st.image(
                            image.copy(),
                            caption=path.name,
                            use_container_width=True,
                        )
                except Exception:
                    st.warning(f"تعذّر فتح {path.name}")
    else:
        st.warning(
            f"لا توجد صور في backgrounds/{folder_name}. "
            "ارفع ملفات الصور إلى المجلد في GitHub."
        )

elif background_mode == "لون رسمي":
    color_label = st.selectbox(
        "اختر اللون",
        list(SOLID_BACKGROUNDS.keys()),
    )
    selected_solid_color = SOLID_BACKGROUNDS[color_label]


# =========================================================
# IMAGE PROCESSING
# =========================================================

if uploaded_file is not None:
    try:
        original = open_uploaded_image(uploaded_file)

        st.subheader("📷 الصورة الأصلية")
        st.image(
            original,
            caption="الصورة قبل المعالجة",
            use_container_width=True,
        )

        process_button = st.button(
            "✨ قصّ الشخص وتطبيق الخلفية",
            type="primary",
            use_container_width=True,
        )

        if process_button:
            if (
                background_mode == "مكتبة الصور"
                and selected_background_path is None
            ):
                st.error(
                    "اختر خلفية من المكتبة أو أضف صورًا إلى مجلدها."
                )

            else:
                with st.spinner(
                    "يجري قصّ الشخص وتجهيز الصورة النهائية..."
                ):
                    subject = remove_background(original)

                    # Use the original dimensions for the final canvas.
                    canvas_size = original.size

                    if background_mode == "مكتبة الصور":
                        background = load_background(
                            selected_background_path,
                            canvas_size,
                        )

                    elif background_mode == "لون رسمي":
                        background = create_solid_background(
                            canvas_size,
                            selected_solid_color,
                        )

                    else:
                        background = create_gradient_background(
                            canvas_size,
                        )

                    result = compose_subject(
                        subject=subject,
                        background=background,
                        subject_width_percent=subject_width,
                        vertical_position=vertical_position,
                        brightness=brightness,
                        contrast=contrast,
                    )

                    st.session_state["last_result"] = result
                    st.session_state["last_original"] = original

        if "last_result" in st.session_state:
            result = st.session_state["last_result"]
            before = st.session_state["last_original"]

            st.divider()
            st.subheader("🔍 مقارنة قبل وبعد")

            col_before, col_after = st.columns(2)

            with col_before:
                st.image(
                    before,
                    caption="قبل",
                    use_container_width=True,
                )

            with col_after:
                st.image(
                    result,
                    caption="بعد",
                    use_container_width=True,
                )

            st.subheader("📥 تنزيل الصورة")

            download_col1, download_col2 = st.columns(2)

            with download_col1:
                st.download_button(
                    "تنزيل JPG",
                    data=image_to_jpeg_bytes(result),
                    file_name="seif_photo_studio.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )

            with download_col2:
                st.download_button(
                    "تنزيل PNG",
                    data=image_to_png_bytes(result),
                    file_name="seif_photo_studio.png",
                    mime="image/png",
                    use_container_width=True,
                )

    except Exception as error:
        st.error(
            "تعذّرت معالجة الصورة. تحقق من حجمها وصيغتها "
            "ومن تثبيت المكتبات المطلوبة."
        )
        st.exception(error)

else:
    st.info(
        "ارفع صورة من القائمة الجانبية لبدء إزالة الخلفية "
        "واختيار خلفية جديدة."
    )


# =========================================================
# STUDIO CONTACT
# =========================================================

st.markdown(
    """
    <div class="studio-footer">
        <h3>SEIF PHOTO STUDIO PRO 📸</h3>
        <p>📍 القلعة الكبرى، سوسة، تونس</p>
        <p>📞 97262953</p>
        <p>تصوير • صور رسمية • معالجة الصور • تغيير الخلفيات</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.link_button(
    "📍 افتح موقع الاستوديو على Google Maps",
    "https://www.google.com/maps/search/?api=1&query=VG9M%2BPVX%2C+Rue+Taher+Sfar%2C+Kala%C3%A2+Kebira",
    use_container_width=True,
)

st.link_button(
    "📞 الاتصال بالاستوديو",
    "tel:97262953",
    use_container_width=True,
)
