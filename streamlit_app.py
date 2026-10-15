
import zipfile
from io import BytesIO

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from rembg import new_session, remove


# =========================================================
# إعداد الصفحة
# =========================================================
st.set_page_config(
    page_title="SEIF PHOTO STUDIO",
    page_icon="📸",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', sans-serif;
    }

    .stApp {
        direction: rtl;
    }

    .stApp h1, .stApp h2, .stApp h3,
    .stApp p, .stApp label {
        text-align: right;
    }

    .hero {
        text-align: center;
        padding: 16px 0 22px;
    }

    .hero h1 {
        margin-bottom: 0;
        letter-spacing: 1px;
    }

    .hero p {
        color: #888;
        margin-top: 6px;
    }

    div.stButton > button,
    div.stDownloadButton > button {
        width: 100%;
        border-radius: 12px;
        font-weight: 700;
        min-height: 44px;
    }

    .contact {
        text-align: center;
        padding: 18px 0;
        border-top: 1px solid #8884;
        margin-top: 30px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>SEIF PHOTO STUDIO 📸</h1>
        <p>استوديو تغيير خلفيات الصور بالذكاء الاصطناعي</p>
        <p>قصّ الخلفية • خلفية بيضاء أو رمادية • مقاسات رسمية</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# الثوابت
# =========================================================
MODELS = {
    "عام (u2net) - متوازن": "u2net",
    "دقة أعلى (isnet-general-use)": "isnet-general-use",
    "أشخاص (u2net_human_seg)": "u2net_human_seg",
    "سريع وخفيف (silueta)": "silueta",
}

COLORS = {
    "رمادي": "#808080",
    "أبيض": "#FFFFFF",
    "أزرق (جواز)": "#2F6FD6",
    "أزرق فاتح": "#BFD9F5",
    "أحمر": "#C62828",
    "أخضر": "#2E7D32",
    "بيج": "#E8DCC8",
    "أسود": "#000000",
    "لون مخصص": None,
}

# النسبة: العرض / الارتفاع
# المقاسات محسوبة تقريبياً على 300 نقطة في البوصة.
CROPS = {
    "أصلي (بدون قص)": (None, None),
    "مربع 1:1": (1.0, None),
    "شخصية 3:4": (3 / 4, None),
    "جواز سفر 35×45 مم": (35 / 45, (413, 531)),
    "صورة 4×6 سم": (4 / 6, (472, 709)),
    "أمريكي 2×2 إنش": (1.0, (600, 600)),
}

BG_MODES = [
    "لون ثابت",
    "تدرّج لوني",
    "صورة خلفية مخصصة",
    "تمويه الخلفية الأصلية",
    "شفاف (PNG)",
]


# =========================================================
# دوال مساعدة
# =========================================================
def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def load_image(data, max_side=2000):
    """فتح الصورة وتصحيح اتجاهها وتقليل حجمها عند الحاجة."""
    with Image.open(BytesIO(data)) as source:
        img = ImageOps.exif_transpose(source).convert("RGBA")

    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    return img


@st.cache_resource(show_spinner="جارٍ تحميل نموذج الذكاء الاصطناعي...")
def get_session(model_name):
    return new_session(model_name)


@st.cache_data(show_spinner=False, max_entries=16)
def cut_subject(data, model, matting, fg_thr, bg_thr, erode, max_side):
    """إزالة خلفية الصورة مع تخزين النتيجة لتسريع التعديلات اللاحقة."""
    original = load_image(data, max_side)
    session = get_session(model)

    kwargs = {"session": session}

    if matting:
        kwargs.update(
            alpha_matting=True,
            alpha_matting_foreground_threshold=fg_thr,
            alpha_matting_background_threshold=bg_thr,
            alpha_matting_erode_size=erode,
        )

    result = remove(original, **kwargs)

    if isinstance(result, Image.Image):
        subject = result.convert("RGBA")
    else:
        with Image.open(BytesIO(result)) as opened:
            subject = opened.convert("RGBA")

    return original, subject


def refine_edges(subject, shrink, feather):
    """تقليل الهالة وتنعيم حواف الشخص."""
    alpha = subject.getchannel("A")

    if shrink > 0:
        alpha = alpha.filter(ImageFilter.MinFilter(shrink * 2 + 1))

    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))

    result = subject.copy()
    result.putalpha(alpha)
    return result


def adjust_subject(subject, brightness, contrast, color):
    """تحسين إضاءة الشخص وألوانه دون تغيير قناة الشفافية."""
    if brightness == contrast == color == 1.0:
        return subject

    alpha = subject.getchannel("A")
    rgb = subject.convert("RGB")

    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    rgb = ImageEnhance.Color(rgb).enhance(color)

    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    return result


def smart_crop_box(subject, ratio, pad):
    """تحديد قص حول الشخص حسب النسبة المطلوبة."""
    alpha = subject.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > 20 else 0)
    bbox = mask.getbbox()

    if not bbox:
        return (0, 0, subject.width, subject.height)

    left, top, right, bottom = bbox
    body_w = right - left
    body_h = bottom - top

    height = body_h * (1 + pad)
    width = height * ratio

    if width < body_w * (1 + pad):
        width = body_w * (1 + pad)
        height = width / ratio

    center_x = (left + right) / 2
    center_y = (top + bottom) / 2

    return (
        int(center_x - width / 2),
        int(center_y - height / 2),
        int(center_x + width / 2),
        int(center_y + height / 2),
    )


def make_gradient(size, color1, color2):
    """إنشاء خلفية متدرجة من الأعلى إلى الأسفل."""
    width, height = size

    start = np.array(hex_to_rgb(color1), dtype=float)
    end = np.array(hex_to_rgb(color2), dtype=float)

    values = np.linspace(0, 1, height)[:, None, None]
    rows = start[None, None, :] * (1 - values) + end[None, None, :] * values
    array = np.broadcast_to(rows, (height, width, 3)).astype(np.uint8).copy()

    return Image.fromarray(array, "RGB").convert("RGBA")


def add_shadow(canvas, subject, opacity, blur, offset):
    """إضافة ظل خفيف خلف الشخص."""
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
    """إنشاء الخلفية المطلوبة."""
    mode = cfg["bg_mode"]

    if mode == "لون ثابت":
        return Image.new(
            "RGBA", size, (*hex_to_rgb(cfg["color"]), 255)
        )

    if mode == "تدرّج لوني":
        return make_gradient(size, cfg["grad1"], cfg["grad2"])

    if mode == "صورة خلفية مخصصة":
        if cfg["bg_bytes"]:
            with Image.open(BytesIO(cfg["bg_bytes"])) as source:
                background = ImageOps.exif_transpose(source).convert("RGBA")

            return ImageOps.fit(
                background, size, method=Image.Resampling.LANCZOS
            )

        return Image.new("RGBA", size, (128, 128, 128, 255))

    if mode == "تمويه الخلفية الأصلية":
        background = ImageOps.fit(
            original, size, method=Image.Resampling.LANCZOS
        )
        return background.filter(
            ImageFilter.GaussianBlur(cfg["blur"])
        ).convert("RGBA")

    if mode == "شفاف (PNG)":
        return Image.new("RGBA", size, (0, 0, 0, 0))

    return Image.new("RGBA", size, (128, 128, 128, 255))


def compose(original, subject, cfg):
    """تركيب الشخص فوق الخلفية مع تطبيق الإعدادات."""
    subject = refine_edges(
        subject, cfg["shrink"], cfg["feather"]
    )

    subject = adjust_subject(
        subject,
        cfg["brightness"],
        cfg["contrast"],
        cfg["color_boost"],
    )

    ratio, target_size = CROPS[cfg["crop"]]

    if ratio:
        box = smart_crop_box(subject, ratio, cfg["pad"])
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

    if cfg["shadow"] and cfg["bg_mode"] != "شفاف (PNG)":
        canvas = add_shadow(
            canvas,
            subject,
            cfg["shadow_opacity"],
            cfg["shadow_blur"],
            cfg["shadow_offset"],
        )

    return Image.alpha_composite(canvas, subject)


def make_sheet(img, sheet_px=(1200, 1800), gap=20):
    """إنشاء ورقة طباعة 4×6 إنش مع تصغير الصور لتناسب الورقة."""
    sheet_w, sheet_h = sheet_px

    # جعل خلفية الطباعة بيضاء حتى عند إدخال صورة شفافة.
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white.alpha_composite(img.convert("RGBA"))
    photo = white.convert("RGB")

    max_w = max(1, sheet_w - 2 * gap)
    max_h = max(1, sheet_h - 2 * gap)

    photo.thumbnail(
        (max_w, max_h), Image.Resampling.LANCZOS
    )

    photo_w, photo_h = photo.size

    cols = max(1, (sheet_w - gap) // (photo_w + gap))
    rows = max(1, (sheet_h - gap) // (photo_h + gap))

    # التأكد من أن كل النسخ تقع داخل حدود الورقة.
    while cols * photo_w + (cols + 1) * gap > sheet_w:
        cols -= 1

    while rows * photo_h + (rows + 1) * gap > sheet_h:
        rows -= 1

    cols = max(1, cols)
    rows = max(1, rows)

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


def encode(img, fmt, quality):
    """تصدير الصورة بالصيغ المختلفة."""
    buffer = BytesIO()

    if fmt == "PNG":
        img.save(buffer, "PNG", dpi=(300, 300))
        return buffer.getvalue(), "image/png", "png"

    if fmt == "WEBP":
        img.convert("RGB").save(
            buffer, "WEBP", quality=quality
        )
        return buffer.getvalue(), "image/webp", "webp"

    img.convert("RGB").save(
        buffer,
        "JPEG",
        quality=quality,
        subsampling=0,
        optimize=True,
        dpi=(300, 300),
    )

    return buffer.getvalue(), "image/jpeg", "jpg"


# =========================================================
# الشريط الجانبي: الإعدادات
# =========================================================
cfg = {}

with st.sidebar:
    st.header("⚙️ إعدادات الصورة")

    with st.expander("🧠 جودة القص", expanded=False):
        model_label = st.selectbox(
            "نموذج الذكاء الاصطناعي", list(MODELS)
        )
        model = MODELS[model_label]

        matting = st.checkbox(
            "حواف دقيقة للشعر (Alpha Matting)",
            value=False,
            help="قد يحسن حواف الشعر، لكنه أبطأ ويستهلك موارد أكثر.",
        )

        fg_thr, bg_thr, erode = 240, 10, 10

        if matting:
            fg_thr = st.slider("عتبة المقدمة", 150, 255, 240)
            bg_thr = st.slider("عتبة الخلفية", 0, 100, 10)
            erode = st.slider("حجم التآكل", 0, 40, 10)

        max_side = st.select_slider(
            "أقصى ضلع للصورة بالبكسل",
            options=[1024, 1600, 2000, 3000, 4000],
            value=2000,
        )

        cfg["shrink"] = st.slider(
            "تضييق الحواف", 0, 5, 1
        )
        cfg["feather"] = st.slider(
            "تنعيم الحواف", 0.0, 5.0, 1.0, 0.5
        )

    with st.expander("🎨 الخلفية", expanded=True):
        cfg["bg_mode"] = st.selectbox(
            "نوع الخلفية", BG_MODES
        )

        cfg.update({
            "color": "#808080",
            "grad1": "#FFFFFF",
            "grad2": "#808080",
            "bg_bytes": None,
            "blur": 25,
        })

        if cfg["bg_mode"] == "لون ثابت":
            color_name = st.selectbox("اختر اللون", list(COLORS))

            if COLORS[color_name] is None:
                cfg["color"] = st.color_picker(
                    "لون مخصص", "#808080"
                )
            else:
                cfg["color"] = COLORS[color_name]

        elif cfg["bg_mode"] == "تدرّج لوني":
            col1, col2 = st.columns(2)

            cfg["grad1"] = col1.color_picker(
                "اللون العلوي", "#FFFFFF"
            )
            cfg["grad2"] = col2.color_picker(
                "اللون السفلي", "#808080"
            )

        elif cfg["bg_mode"] == "صورة خلفية مخصصة":
            bg_file = st.file_uploader(
                "ارفع صورة الخلفية",
                type=["jpg", "jpeg", "png", "webp"],
                key="bgfile",
            )

            cfg["bg_bytes"] = (
                bg_file.getvalue() if bg_file else None
            )

            if not bg_file:
                st.info("ارفع خلفية مخصصة أو اختر نوعًا آخر.")

        elif cfg["bg_mode"] == "تمويه الخلفية الأصلية":
            cfg["blur"] = st.slider(
                "قوة التمويه", 5, 80, 25
            )

    with st.expander("✨ تحسين الشخص"):
        cfg["brightness"] = st.slider(
            "السطوع", 0.5, 1.5, 1.0, 0.05
        )
        cfg["contrast"] = st.slider(
            "التباين", 0.5, 1.5, 1.0, 0.05
        )
        cfg["color_boost"] = st.slider(
            "تشبّع الألوان", 0.0, 2.0, 1.0, 0.05
        )

        cfg["shadow"] = st.checkbox(
            "إضافة ظل ناعم", value=False
        )

        cfg["shadow_opacity"] = 0.4
        cfg["shadow_blur"] = 20
        cfg["shadow_offset"] = 15

        if cfg["shadow"]:
            cfg["shadow_opacity"] = st.slider(
                "شفافية الظل", 0.1, 1.0, 0.4, 0.05
            )
            cfg["shadow_blur"] = st.slider(
                "نعومة الظل", 2, 60, 20
            )
            cfg["shadow_offset"] = st.slider(
                "إزاحة الظل", 0, 60, 15
            )

    with st.expander("✂️ القص والمقاسات"):
        cfg["crop"] = st.selectbox(
            "مقاس الصورة", list(CROPS)
        )

        cfg["pad"] = st.slider(
            "المساحة حول الشخص", 0.0, 0.6, 0.2, 0.05
        )

        make_print_sheet = False

        if CROPS[cfg["crop"]][1]:
            make_print_sheet = st.checkbox(
                "إنشاء ورقة طباعة 4×6 إنش بعدة نسخ",
                value=False,
            )

    with st.expander("💾 التصدير"):
        out_fmt = st.radio(
            "صيغة الصورة",
            ["JPEG", "PNG", "WEBP"],
            horizontal=True,
        )

        quality = (
            st.slider("جودة التصدير", 60, 100, 95)
            if out_fmt != "PNG"
            else 95
        )

        if cfg["bg_mode"] == "شفاف (PNG)":
            out_fmt = "PNG"
            st.caption("الخلفية الشفافة تتطلب صيغة PNG.")


# =========================================================
# رفع الصور ومعالجتها
# =========================================================
photos = st.file_uploader(
    "📤 اختر صورة واحدة أو عدة صور",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if photos:
    with st.expander(
        f"معاينة الصور المرفوعة ({len(photos)})",
        expanded=False,
    ):
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

    progress = st.progress(
        0.0, text="جارٍ تجهيز الصور..."
    )

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
                original.copy(), subject.copy(), cfg
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
                    make_sheet(final_image),
                    "JPEG",
                    95,
                )
                item["sheet"] = sheet_data

            results.append(item)

        except Exception as error:
            st.error(
                f"تعذّرت معالجة الصورة «{photo.name}». "
                f"التفاصيل: {error}"
            )

        progress.progress(
            (index + 1) / len(photos),
            text=f"تمت معالجة {index + 1} من {len(photos)}",
        )

    progress.empty()
    st.session_state["results"] = results


# =========================================================
# عرض النتائج وتنزيلها
# =========================================================
results = st.session_state.get("results", [])

if results:
    st.success(f"تمت معالجة {len(results)} صورة بنجاح ✅")

    for index, result in enumerate(results):
        st.markdown(f"### {result['name']}")

        col_before, col_after = st.columns(2)

        col_before.image(
            result["before"],
            caption="قبل التعديل",
            use_container_width=True,
        )

        col_after.image(
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
        )

        if "sheet" in result:
            download_cols[1].download_button(
                "🖨️ تنزيل ورقة الطباعة 4×6",
                data=result["sheet"],
                file_name=(
                    result["name"].rsplit(".", 1)[0]
                    + "-sheet.jpg"
                ),
                mime="image/jpeg",
                key=f"sheet_{index}",
            )

        st.divider()

    if len(results) > 1:
        zip_buffer = BytesIO()

        with zipfile.ZipFile(
            zip_buffer, "w", zipfile.ZIP_DEFLATED
        ) as archive:
            for result in results:
                archive.writestr(
                    result["name"], result["data"]
                )

        st.download_button(
            "📦 تنزيل كل الصور في ملف ZIP",
            data=zip_buffer.getvalue(),
            file_name="seif-photos.zip",
            mime="application/zip",
            use_container_width=True,
        )

elif not photos:
    st.info(
        "ارفع صورة من الأعلى، ثم اختر الخلفية والإعدادات "
        "من الشريط الجانبي."
    )


# =========================================================
# معلومات الاستوديو
# =========================================================
st.markdown(
    """
    <div class="contact">
        <h3>SEIF PHOTO STUDIO 📸</h3>
        <p>📍 القلعة الكبرى، سوسة، تونس</p>
        <p>📞 97262953</p>
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
