
import io
import zipfile
import hashlib
from io import BytesIO

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from rembg import new_session, remove


# =========================================================
# 1. إعداد الصفحة
# =========================================================
st.set_page_config(
    page_title="SEIF PHOTO STUDIO PRO",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded",
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

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    font-family: 'Cairo', sans-serif !important;
    background: var(--studio-bg) !important;
    color: var(--studio-text) !important;
}

.stApp {
    direction: rtl;
}

[data-testid="stHeader"] {
    background: rgba(16,17,20,0.96) !important;
}

[data-testid="stSidebar"] {
    background: #17191E !important;
    border-left: 1px solid var(--studio-border);
}

[data-testid="stSidebar"] * {
    color: var(--studio-text);
}

.stApp h1, .stApp h2, .stApp h3,
.stApp p, .stApp label,
[data-testid="stMarkdownContainer"] {
    color: var(--studio-text);
}

.hero {
    text-align: center;
    padding: 24px 12px;
    margin: 10px 0 25px;
    background: linear-gradient(135deg, #1B1D22, #252018);
    border: 1px solid #6D5926;
    border-radius: 20px;
}

.hero h1 {
    color: var(--studio-gold) !important;
    font-weight: 800;
    margin-bottom: 8px;
}

.hero p {
    color: var(--studio-muted) !important;
    margin: 4px 0;
}

.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {
    border-radius: 12px !important;
    font-weight: 700 !important;
    min-height: 44px;
    transition: border-color .2s ease, background .2s ease;
}

.stButton > button[kind="primary"] {
    background: var(--studio-gold) !important;
    color: #171717 !important;
    border: 1px solid var(--studio-gold) !important;
}

.stButton > button[kind="primary"]:hover {
    background: var(--studio-gold-hover) !important;
    border-color: var(--studio-gold-hover) !important;
}

.stButton > button:not([kind="primary"]),
.stDownloadButton > button,
.stLinkButton > a {
    background: var(--studio-panel) !important;
    color: var(--studio-text) !important;
    border: 1px solid var(--studio-border) !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
.stLinkButton > a:hover {
    border-color: var(--studio-gold) !important;
}

[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpander"] {
    border-color: var(--studio-border) !important;
    border-radius: 14px !important;
}

[data-testid="stFileUploader"] {
    background: #181A1F;
    border: 1px dashed #6D5926;
    border-radius: 14px;
    padding: 10px;
}

input, textarea,
[data-baseweb="select"] > div {
    border-radius: 10px !important;
}

.stProgress > div > div > div {
    background-color: var(--studio-gold) !important;
}

.contact {
    text-align: center;
    padding: 22px 10px;
    margin-top: 35px;
    border-top: 1px solid var(--studio-border);
    color: var(--studio-muted);
}

.contact h3 {
    color: var(--studio-gold) !important;
}

img {
    border-radius: 10px;
}

hr {
    border-color: var(--studio-border) !important;
}

@media (max-width: 768px) {
    .hero {
        padding: 16px 8px;
        margin: 5px 0 18px;
    }

    .hero h1 {
        font-size: 1.7rem;
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>SEIF PHOTO STUDIO PRO 📸</h1>
    <p>استوديو احترافي لمعالجة الصور وتغيير الخلفيات</p>
    <p>قصّ ذكي • صور رسمية • خلفيات مخصصة • تحسين الإضاءة • طباعة</p>
</div>
""", unsafe_allow_html=True)


# =========================================================
# 2. الثوابت والإعدادات
# =========================================================
MODELS = {
    "متوازن - u2net": "u2net",
    "دقة أعلى - isnet-general-use": "isnet-general-use",
    "خاص بالأشخاص - u2net_human_seg": "u2net_human_seg",
    "خفيف - silueta": "silueta",
}

COLORS = {
    "رمادي": "#808080",
    "أبيض": "#FFFFFF",
    "أزرق رسمي": "#2F6FD6",
    "أزرق فاتح": "#BFD9F5",
    "أحمر": "#C62828",
    "أخضر": "#2E7D32",
    "بيج": "#E8DCC8",
    "أسود": "#000000",
    "لون مخصص": None,
}

CROPS = {
    "أصلي بدون قص": (None, None),
    "مربع 1:1": (1.0, None),
    "شخصية 3:4": (3 / 4, None),
    "جواز سفر 35×45 مم": (35 / 45, (413, 531)),
    "صورة 4×6 سم": (4 / 6, (472, 709)),
    "أمريكي 2×2 إنش": (1.0, (600, 600)),
}

BG_MODES = [
    "لون ثابت",
    "تدرج لوني",
    "صورة خلفية مخصصة",
    "تمويه الخلفية الأصلية",
    "شفاف PNG",
]


# =========================================================
# 3. دوال الصور
# =========================================================
def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def load_image(data, max_side=2000):
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")

    if max_side and max(image.size) > max_side:
        image.thumbnail(
            (max_side, max_side),
            Image.Resampling.LANCZOS,
        )

    return image


@st.cache_resource(show_spinner="تحميل نموذج الذكاء الاصطناعي...")
def get_session(model_name):
    return new_session(model_name)


@st.cache_data(show_spinner=False, max_entries=12)
def cut_subject(data, model, matting, fg_thr, bg_thr, erode, max_side):
    original = load_image(data, max_side)
    session = get_session(model)

    options = {"session": session}

    if matting:
        options.update(
            alpha_matting=True,
            alpha_matting_foreground_threshold=fg_thr,
            alpha_matting_background_threshold=bg_thr,
            alpha_matting_erode_size=erode,
        )

    result = remove(original, **options)

    if isinstance(result, Image.Image):
        subject = result.convert("RGBA")
    else:
        with Image.open(BytesIO(result)) as source:
            subject = source.convert("RGBA")

    return original, subject


def refine_edges(subject, shrink=1, feather=1.0):
    alpha = subject.getchannel("A")

    if shrink > 0:
        alpha = alpha.filter(
            ImageFilter.MinFilter(shrink * 2 + 1)
        )

    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))

    result = subject.copy()
    result.putalpha(alpha)
    return result


def adjust_subject(subject, brightness, contrast, saturation):
    alpha = subject.getchannel("A")
    rgb = subject.convert("RGB")

    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    rgb = ImageEnhance.Color(rgb).enhance(saturation)

    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    return result


def smart_crop_box(subject, ratio, pad, vertical_position=0.5):
    alpha = subject.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > 20 else 0)
    bbox = mask.getbbox()

    if not bbox:
        return (0, 0, subject.width, subject.height)

    left, top, right, bottom = bbox
    body_w = right - left
    body_h = bottom - top

    crop_h = body_h * (1 + pad)
    crop_w = crop_h * ratio

    if crop_w < body_w * (1 + pad):
        crop_w = body_w * (1 + pad)
        crop_h = crop_w / ratio

    center_x = (left + right) / 2

    # ضبط موضع القص رأسيًا: 0 أعلى، 0.5 وسط، 1 أسفل.
    center_y = top + body_h * vertical_position

    x1 = int(center_x - crop_w / 2)
    y1 = int(center_y - crop_h * vertical_position)
    x2 = int(x1 + crop_w)
    y2 = int(y1 + crop_h)

    return (x1, y1, x2, y2)


def make_gradient(size, color1, color2):
    width, height = size

    start = np.array(hex_to_rgb(color1), dtype=float)
    end = np.array(hex_to_rgb(color2), dtype=float)

    values = np.linspace(0, 1, height)[:, None, None]
    rows = start[None, None, :] * (1 - values) + end[None, None, :] * values

    array = np.broadcast_to(
        rows, (height, width, 3)
    ).astype(np.uint8).copy()

    return Image.fromarray(array, "RGB").convert("RGBA")


def add_shadow(canvas, subject, opacity, blur, offset):
    alpha = subject.getchannel("A").point(
        lambda value: int(value * opacity)
    )

    shadow = Image.new("RGBA", subject.size, (0, 0, 0, 255))
    shadow.putalpha(alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(shadow, (offset, offset))

    return Image.alpha_composite(canvas, layer)


def build_background(size, cfg, original):
    mode = cfg["bg_mode"]

    if mode == "لون ثابت":
        return Image.new(
            "RGBA", size, (*hex_to_rgb(cfg["color"]), 255)
        )

    if mode == "تدرج لوني":
        return make_gradient(size, cfg["grad1"], cfg["grad2"])

    if mode == "صورة خلفية مخصصة":
        if cfg["bg_bytes"]:
            with Image.open(BytesIO(cfg["bg_bytes"])) as source:
                background = ImageOps.exif_transpose(source).convert("RGBA")

            return ImageOps.fit(
                background, size,
                method=Image.Resampling.LANCZOS,
            )

        return Image.new("RGBA", size, (128, 128, 128, 255))

    if mode == "تمويه الخلفية الأصلية":
        background = ImageOps.fit(
            original, size,
            method=Image.Resampling.LANCZOS,
        )
        return background.filter(
            ImageFilter.GaussianBlur(cfg["blur"])
        ).convert("RGBA")

    if mode == "شفاف PNG":
        return Image.new("RGBA", size, (0, 0, 0, 0))

    return Image.new("RGBA", size, (128, 128, 128, 255))


def compose(original, subject, cfg):
    subject = refine_edges(
        subject, cfg["shrink"], cfg["feather"]
    )

    subject = adjust_subject(
        subject,
        cfg["brightness"],
        cfg["contrast"],
        cfg["saturation"],
    )

    ratio, target_size = CROPS[cfg["crop"]]

    if ratio:
        box = smart_crop_box(
            subject,
            ratio,
            cfg["pad"],
            cfg["vertical_position"],
        )

        subject = subject.crop(box)
        original = original.crop(box)

        if target_size:
            subject = subject.resize(
                target_size, Image.Resampling.LANCZOS
            )
            original = original.resize(
                target_size, Image.Resampling.LANCZOS
            )

    canvas = build_background(subject.size, cfg, original)

    if cfg["shadow"] and cfg["bg_mode"] != "شفاف PNG":
        canvas = add_shadow(
            canvas,
            subject,
            cfg["shadow_opacity"],
            cfg["shadow_blur"],
            cfg["shadow_offset"],
        )

    return Image.alpha_composite(canvas, subject)


def make_sheet(image, sheet_px=(1200, 1800), gap=20):
    sheet_w, sheet_h = sheet_px

    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    white.alpha_composite(image.convert("RGBA"))
    photo = white.convert("RGB")

    photo.thumbnail(
        (sheet_w - 2 * gap, sheet_h - 2 * gap),
        Image.Resampling.LANCZOS,
    )

    photo_w, photo_h = photo.size
    cols = max(1, (sheet_w - gap) // (photo_w + gap))
    rows = max(1, (sheet_h - gap) // (photo_h + gap))

    while cols > 1 and cols * photo_w + (cols + 1) * gap > sheet_w:
        cols -= 1

    while rows > 1 and rows * photo_h + (rows + 1) * gap > sheet_h:
        rows -= 1

    sheet = Image.new("RGB", sheet_px, "white")

    total_w = cols * photo_w + (cols - 1) * gap
    total_h = rows * photo_h + (rows - 1) * gap
    start_x = (sheet_w - total_w) // 2
    start_y = (sheet_h - total_h) // 2

    for row in range(rows):
        for col in range(cols):
            x = start_x + col * (photo_w + gap)
            y = start_y + row * (photo_h + gap)
            sheet.paste(photo, (x, y))

    return sheet


def encode(image, fmt, quality):
    buffer = BytesIO()

    if fmt == "PNG":
        image.save(buffer, "PNG", dpi=(300, 300))
        return buffer.getvalue(), "image/png", "png"

    if fmt == "WEBP":
        image.convert("RGB").save(
            buffer, "WEBP", quality=quality
        )
        return buffer.getvalue(), "image/webp", "webp"

    image.convert("RGB").save(
        buffer,
        "JPEG",
        quality=quality,
        subsampling=0,
        optimize=True,
        dpi=(300, 300),
    )

    return buffer.getvalue(), "image/jpeg", "jpg"


# =========================================================
# 4. إعدادات الاستوديو
# =========================================================
cfg = {}

with st.sidebar:
    st.markdown("## ⚙️ إعدادات الاستوديو")

    with st.expander("🧠 الذكاء الاصطناعي والقص", expanded=True):
        model_label = st.selectbox(
            "نموذج إزالة الخلفية", list(MODELS)
        )
        model = MODELS[model_label]

        matting = st.checkbox(
            "تحسين حواف الشعر والتفاصيل",
            value=False,
        )

        fg_thr, bg_thr, erode = 240, 10, 10

        if matting:
            fg_thr = st.slider("عتبة المقدمة", 150, 255, 240)
            bg_thr = st.slider("عتبة الخلفية", 0, 100, 10)
            erode = st.slider("حجم تحسين الحواف", 0, 40, 10)

        max_side = st.select_slider(
            "أقصى حجم للصورة",
            options=[1024, 1600, 2000, 3000, 4000],
            value=2000,
        )

        cfg["shrink"] = st.slider(
            "تقليل الهالة حول الشخص", 0, 5, 1
        )
        cfg["feather"] = st.slider(
            "تنعيم الحواف", 0.0, 5.0, 1.0, 0.5
        )

    with st.expander("🎨 الخلفيات", expanded=True):
        cfg["bg_mode"] = st.selectbox("نوع الخلفية", BG_MODES)

        cfg.update({
            "color": "#808080",
            "grad1": "#FFFFFF",
            "grad2": "#808080",
            "bg_bytes": None,
            "blur": 25,
        })

        if cfg["bg_mode"] == "لون ثابت":
            color_name = st.selectbox("لون الخلفية", list(COLORS))

            cfg["color"] = (
                st.color_picker("اختر لونًا مخصصًا", "#808080")
                if COLORS[color_name] is None
                else COLORS[color_name]
            )

        elif cfg["bg_mode"] == "تدرج لوني":
            col1, col2 = st.columns(2)
            cfg["grad1"] = col1.color_picker("اللون الأول", "#FFFFFF")
            cfg["grad2"] = col2.color_picker("اللون الثاني", "#808080")

        elif cfg["bg_mode"] == "صورة خلفية مخصصة":
            bg_file = st.file_uploader(
                "ارفع صورة الخلفية",
                type=["jpg", "jpeg", "png", "webp"],
                key="custom_background",
            )
            cfg["bg_bytes"] = bg_file.getvalue() if bg_file else None

            if not bg_file:
                st.info("يمكنك رفع خلفية من جهازك.")

        elif cfg["bg_mode"] == "تمويه الخلفية الأصلية":
            cfg["blur"] = st.slider("قوة التمويه", 5, 80, 25)

    with st.expander("✨ تحسين الإضاءة والألوان"):
        cfg["brightness"] = st.slider(
            "الإضاءة", 0.5, 1.5, 1.0, 0.05
        )
        cfg["contrast"] = st.slider(
            "التباين", 0.5, 1.5, 1.0, 0.05
        )
        cfg["saturation"] = st.slider(
            "تشبع الألوان", 0.0, 2.0, 1.0, 0.05
        )

        cfg["shadow"] = st.checkbox("إضافة ظل ناعم", value=False)
        cfg["shadow_opacity"] = 0.4
        cfg["shadow_blur"] = 20
        cfg["shadow_offset"] = 15

        if cfg["shadow"]:
            cfg["shadow_opacity"] = st.slider(
                "قوة الظل", 0.1, 1.0, 0.4, 0.05
            )
            cfg["shadow_blur"] = st.slider(
                "نعومة الظل", 2, 60, 20
            )
            cfg["shadow_offset"] = st.slider(
                "إزاحة الظل", 0, 60, 15
            )

    with st.expander("✂️ القص والمقاسات الرسمية"):
        cfg["crop"] = st.selectbox("مقاس الصورة", list(CROPS))
        cfg["pad"] = st.slider(
            "المساحة حول الشخص", 0.0, 0.8, 0.2, 0.05
        )
        cfg["vertical_position"] = st.slider(
            "موضع القص رأسيًا",
            0.0, 1.0, 0.5, 0.05,
            help="حرّك القص إلى الأعلى أو الأسفل إذا لزم.",
        )

        make_print_sheet = False

        if CROPS[cfg["crop"]][1]:
            make_print_sheet = st.checkbox(
                "إنشاء ورقة طباعة 4×6 إنش",
                value=False,
            )

    with st.expander("💾 التصدير"):
        out_fmt = st.radio(
            "صيغة الصورة",
            ["JPEG", "PNG", "WEBP"],
            horizontal=True,
        )

        quality = (
            st.slider("جودة الصورة", 60, 100, 95)
            if out_fmt != "PNG" else 95
        )

        if cfg["bg_mode"] == "شفاف PNG":
            out_fmt = "PNG"
            st.caption("تم اختيار PNG للحفاظ على الشفافية.")


# =========================================================
# 5. رفع الصور ومعالجتها
# =========================================================
photos = st.file_uploader(
    "📤 ارفع صورة واحدة أو عدة صور",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="يمكنك اختيار عدة صور لمعالجتها دفعة واحدة.",
)

if photos:
    with st.expander(f"معاينة الصور المرفوعة ({len(photos)})"):
        preview_cols = st.columns(min(len(photos), 5))

        for index, photo in enumerate(photos):
            preview_cols[index % len(preview_cols)].image(
                photo,
                caption=photo.name,
                use_container_width=True,
            )

run = st.button(
    "🪄 إزالة الخلفية وتغييرها",
    type="primary",
    disabled=not photos,
    use_container_width=True,
)

if run and photos:
    results = []
    progress = st.progress(0.0, text="جارٍ تجهيز الصور...")

    for index, photo in enumerate(photos):
        try:
            original, subject = cut_subject(
                photo.getvalue(),
                model,
                matting,
                fg_thr,
                bg_thr,
                erode,
                max_side,
            )

            final_image = compose(
                original.copy(),
                subject.copy(),
                cfg,
            )

            data, mime, extension = encode(
                final_image, out_fmt, quality
            )

            base_name = photo.name.rsplit(".", 1)[0]

            item = {
                "name": f"{base_name}-seif.{extension}",
                "mime": mime,
                "data": data,
                "before": original,
                "after": final_image,
            }

            if make_print_sheet:
                sheet_data, _, _ = encode(
                    make_sheet(final_image), "JPEG", 95
                )
                item["sheet"] = sheet_data

            results.append(item)

        except Exception as error:
            st.error(
                f"تعذّرت معالجة {photo.name}: {error}"
            )

        progress.progress(
            (index + 1) / len(photos),
            text=f"معالجة الصورة {index + 1} من {len(photos)}",
        )

    progress.empty()
    st.session_state["results"] = results


# =========================================================
# 6. النتائج والتنزيل
# =========================================================
results = st.session_state.get("results", [])

if results:
    st.success(f"اكتملت معالجة {len(results)} صورة بنجاح ✅")

    for index, result in enumerate(results):
        st.markdown(f"### 📷 {result['name']}")

        col_before, col_after = st.columns(2)

        with col_before:
            st.image(
                result["before"],
                caption="قبل التعديل",
                use_container_width=True,
            )

        with col_after:
            st.image(
                result["after"],
                caption="بعد التعديل",
                use_container_width=True,
            )

        download_cols = st.columns(2)

        download_cols[0].download_button(
            "⬇️ تنزيل الصورة",
            data=result["data"],
            file_name=result["name"],
            mime=result["mime"],
            key=f"download_{index}",
            use_container_width=True,
        )

        if "sheet" in result:
            download_cols[1].download_button(
                "🖨️ تنزيل ورقة الطباعة",
                data=result["sheet"],
                file_name=f"sheet-{index + 1}.jpg",
                mime="image/jpeg",
                key=f"sheet_{index}",
                use_container_width=True,
            )

        st.divider()

    if len(results) > 1:
        zip_buffer = BytesIO()

        with zipfile.ZipFile(
            zip_buffer, "w", zipfile.ZIP_DEFLATED
        ) as archive:
            for result in results:
                archive.writestr(result["name"], result["data"])

        st.download_button(
            "📦 تنزيل كل الصور في ملف ZIP",
            data=zip_buffer.getvalue(),
            file_name="seif-photos.zip",
            mime="application/zip",
            use_container_width=True,
        )

elif not photos:
    st.info(
        "ارفع صورة من الأعلى، ثم اختر الخلفية والمقاس "
        "والإعدادات من الشريط الجانبي."
    )


# =========================================================
# 7. معلومات الاستوديو
# =========================================================
st.markdown("""
<div class="contact">
    <h3>SEIF PHOTO STUDIO PRO 📸</h3>
    <p>📍 القلعة الكبرى، سوسة، تونس</p>
    <p>📞 97262953</p>
    <p>تصوير • صور رسمية • معالجة الصور • تغيير الخلفيات</p>
</div>
""", unsafe_allow_html=True)

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
