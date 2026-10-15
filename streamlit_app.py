
import base64
import hashlib
import io
import os
import re
import tempfile
import time

import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageEnhance, ImageOps
from rembg import new_session, remove
streamlit-cropper
# =========================================================
# SEIF PHOTO STUDIO PRO
# =========================================================

MAX_SIDE = 1800
OWNER_EMAIL = "seifjaballah77@gmail.com"
PHONE = "97262953"
PHONE_INTL = "+21697262953"

MAPS_URL = (
    "https://www.google.com/maps/search/?api=1&query="
    "VG9M%2BPVX%2C+Rue+Taher+Sfar%2C+Kal%C3%A2a+Kebira"
)

EMAILJS_URL = "https://api.emailjs.com/api/v1.0/email/send"
FEEDBACK_COOLDOWN = 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

CUSTOM_COLOR_MODE = "لون مخصص"
CUSTOM_IMAGE_MODE = "صورة خلفية مخصصة"

PRESET_COLORS = {
    "رمادي": "#808080",
    "أبيض": "#FFFFFF",
    "أسود": "#000000",
    "أزرق فاتح": "#A9C7E8",
    "بيج": "#D8C3A5",
}

BACKGROUND_OPTIONS = [
    *PRESET_COLORS,
    CUSTOM_COLOR_MODE,
    CUSTOM_IMAGE_MODE,
]


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="SEIF PHOTO STUDIO PRO",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #111111;
        color: white;
    }

    h1, h2, h3 {
        color: #D4AF37 !important;
    }

    .stButton button,
    .stDownloadButton button,
    .stLinkButton a {
        border-radius: 12px;
        font-weight: 700;
        min-height: 44px;
    }

    section[data-testid="stSidebar"] {
        background: #1B1B1B;
    }

    img {
        max-width: 100%;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    @media (max-width: 640px) {
        .block-container {
            padding: 1rem 0.7rem;
        }

        h1 {
            font-size: 1.65rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📸 SEIF PHOTO STUDIO PRO")
st.subheader("Professional Photo Background Studio")
st.write(
    "تغيير الخلفيات، القصّ الدقيق، تحريك الشخص، "
    "التدوير، التكبير وتحسين الصورة."
)


# =========================================================
# DIRECT-DRAG COMPONENT
# A small HTML component for moving the cutout with a mouse
# or a finger. Coordinates are returned to Streamlit.
# =========================================================

COMPONENT_DIR = os.path.join(
    tempfile.gettempdir(),
    "seif_photo_drag_component",
)
os.makedirs(COMPONENT_DIR, exist_ok=True)

COMPONENT_HTML = os.path.join(COMPONENT_DIR, "index.html")

DRAG_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    background: transparent;
    overflow: hidden;
    font-family: sans-serif;
}
#hint {
    color: #D4AF37;
    font-size: 14px;
    margin: 0 0 8px 0;
}
#wrap {
    width: 100%;
    display: flex;
    justify-content: center;
}
canvas {
    display: block;
    max-width: 100%;
    border: 2px solid #D4AF37;
    border-radius: 8px;
    touch-action: none;
    cursor: grab;
}
canvas.dragging {
    cursor: grabbing;
}
</style>
</head>
<body>
<p id="hint">اسحب الشخص بالفأرة أو بإصبعك لتغيير موضعه.</p>
<div id="wrap"><canvas id="canvas"></canvas></div>

<script>
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

let background = new Image();
let subject = new Image();

let args = {};
let x = 0.5;
let y = 0.5;
let dragging = false;
let offsetX = 0;
let offsetY = 0;
let subjectW = 0;
let subjectH = 0;
let ready = false;
let lastRenderKey = "";

function send(type, data) {
    window.parent.postMessage(
        {
            isStreamlitMessage: true,
            type: type,
            ...data
        },
        "*"
    );
}

function setHeight() {
    send("streamlit:setFrameHeight", {
        height: canvas.height + 42
    });
}

function clampPosition() {
    const maxX = Math.max(0, canvas.width - subjectW);
    const maxY = Math.max(0, canvas.height - subjectH);

    x = Math.min(1, Math.max(0, x));
    y = Math.min(1, Math.max(0, y));

    return {
        px: x * maxX,
        py: y * maxY,
        maxX: maxX,
        maxY: maxY
    };
}

function draw() {
    if (!ready) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(background, 0, 0, canvas.width, canvas.height);

    const pos = clampPosition();

    ctx.drawImage(
        subject,
        pos.px,
        pos.py,
        subjectW,
        subjectH
    );

    setHeight();
}

function emitPosition() {
    const pos = clampPosition();

    send("streamlit:setComponentValue", {
        value: {
            x: pos.maxX ? pos.px / pos.maxX : 0,
            y: pos.maxY ? pos.py / pos.maxY : 0
        },
        dataType: "json"
    });
}

function loadArgs(newArgs) {
    args = newArgs;

    const renderKey = [
        args.background,
        args.subject,
        args.width,
        args.height,
        args.subject_width,
        args.subject_height,
        args.x,
        args.y
    ].join("|");

    if (renderKey === lastRenderKey) return;
    lastRenderKey = renderKey;

    ready = false;
    background = new Image();
    subject = new Image();

    canvas.width = args.width;
    canvas.height = args.height;

    x = Number(args.x ?? 0.5);
    y = Number(args.y ?? 0.5);

    subjectW = Math.min(
        canvas.width,
        Number(args.subject_width)
    );
    subjectH = Math.min(
        canvas.height,
        Number(args.subject_height)
    );

    let loaded = 0;

    function onLoaded() {
        loaded += 1;

        if (loaded === 2) {
            ready = true;
            draw();
        }
    }

    background.onload = onLoaded;
    subject.onload = onLoaded;

    background.onerror = function() {
        document.getElementById("hint").textContent =
            "تعذّر تحميل معاينة الخلفية.";
    };

    subject.onerror = function() {
        document.getElementById("hint").textContent =
            "تعذّر تحميل صورة الشخص.";
    };

    background.src = args.background;
    subject.src = args.subject;
}

canvas.addEventListener("pointerdown", function(event) {
    if (!ready) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const mouseX = (event.clientX - rect.left) * scaleX;
    const mouseY = (event.clientY - rect.top) * scaleY;

    const pos = clampPosition();

    if (
        mouseX >= pos.px &&
        mouseX <= pos.px + subjectW &&
        mouseY >= pos.py &&
        mouseY <= pos.py + subjectH
    ) {
        dragging = true;
        offsetX = mouseX - pos.px;
        offsetY = mouseY - pos.py;
        canvas.classList.add("dragging");
        canvas.setPointerCapture(event.pointerId);
    }
});

canvas.addEventListener("pointermove", function(event) {
    if (!dragging || !ready) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const mouseX = (event.clientX - rect.left) * scaleX;
    const mouseY = (event.clientY - rect.top) * scaleY;

    const maxX = Math.max(0, canvas.width - subjectW);
    const maxY = Math.max(0, canvas.height - subjectH);

    const px = Math.max(
        0, Math.min(maxX, mouseX - offsetX)
    );
    const py = Math.max(
        0, Math.min(maxY, mouseY - offsetY)
    );

    x = maxX ? px / maxX : 0;
    y = maxY ? py / maxY : 0;

    draw();
});

function stopDragging() {
    if (!dragging) return;

    dragging = false;
    canvas.classList.remove("dragging");
    emitPosition();
}

canvas.addEventListener("pointerup", stopDragging);
canvas.addEventListener("pointercancel", stopDragging);
canvas.addEventListener("lostpointercapture", stopDragging);

window.addEventListener("message", function(event) {
    const data = event.data;

    if (!data || data.type !== "streamlit:render") return;

    loadArgs(data.args || {});
});

send("streamlit:componentReady", {
    apiVersion: 1
});

send("streamlit:setFrameHeight", {
    height: 450
});
</script>
</body>
</html>
"""

with open(COMPONENT_HTML, "w", encoding="utf-8") as html_file:
    html_file.write(DRAG_HTML)

drag_position = components.declare_component(
    "seif_photo_drag_position",
    path=COMPONENT_DIR,
)


# =========================================================
# IMAGE HELPERS
# =========================================================

def load_image(source):
    image = Image.open(source)
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def limit_size(image, max_side=MAX_SIDE):
    image = image.copy()
    image.thumbnail(
        (max_side, max_side),
        Image.Resampling.LANCZOS,
    )
    return image


@st.cache_resource
def load_model():
    return new_session("u2net")


def remove_photo_background(image):
    result = remove(
        image.convert("RGBA"),
        session=load_model(),
    )

    if isinstance(result, bytes):
        result = Image.open(io.BytesIO(result))

    return result.convert("RGBA")


def get_cutout(image, file_hash):
    cache_key = "cutout_" + file_hash

    if cache_key not in st.session_state:
        st.session_state[cache_key] = remove_photo_background(image)

    return st.session_state[cache_key]


def rotate_photo(image, angle):
    angle = angle % 360

    if angle == 0:
        return image.copy()

    return image.rotate(
        -angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )


def get_subject(cutout, rotation, zoom_level, canvas_size):
    """
    استخراج حدود الشخص الشفافة، ثم تدويره وتغيير حجمه.
    لا نكبر صورة الشخص الشفافة الكاملة لأن ذلك يسبب فراغات كبيرة.
    """
    rotated = rotate_photo(cutout, rotation)
    alpha = rotated.getchannel("A")
    bbox = alpha.getbbox()

    if bbox is None:
        raise ValueError("لم يتم العثور على شخص واضح في الصورة.")

    subject = rotated.crop(bbox)

    # ثمانية مستويات للتكبير.
    zoom_factor = 0.65 + (zoom_level - 1) * 0.10

    new_width = max(1, int(subject.width * zoom_factor))
    new_height = max(1, int(subject.height * zoom_factor))

    subject = subject.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )

    # منع تجاوز أبعاد لوحة الخلفية.
    max_width, max_height = canvas_size

    fit_factor = min(
        1.0,
        max_width / subject.width,
        max_height / subject.height,
    )

    if fit_factor < 1:
        subject = subject.resize(
            (
                max(1, int(subject.width * fit_factor)),
                max(1, int(subject.height * fit_factor)),
            ),
            Image.Resampling.LANCZOS,
        )

    return subject


def make_background(size, mode, custom_color, bg_image=None):
    if mode == CUSTOM_IMAGE_MODE:
        if bg_image is None:
            raise ValueError("ارفع صورة الخلفية أولًا.")

        return ImageOps.fit(
            bg_image.convert("RGB"),
            size,
            method=Image.Resampling.LANCZOS,
        ).convert("RGBA")

    color = (
        custom_color
        if mode == CUSTOM_COLOR_MODE
        else PRESET_COLORS.get(mode, "#808080")
    )

    return Image.new("RGBA", size, color)


def compose_photo(background, subject, x_position, y_position):
    """
    x_position و y_position من 0 إلى 1.
    يحددان مكان الشخص ضمن المساحة المتاحة.
    """
    canvas = background.copy()

    max_x = max(0, canvas.width - subject.width)
    max_y = max(0, canvas.height - subject.height)

    x = int(max_x * min(1, max(0, x_position)))
    y = int(max_y * min(1, max(0, y_position)))

    canvas.alpha_composite(subject, dest=(x, y))

    return canvas.convert("RGB")


def improve_photo(image, brightness, contrast, sharpness):
    result = image.convert("RGB")

    if brightness != 1.0:
        result = ImageEnhance.Brightness(result).enhance(brightness)

    if contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(contrast)

    if sharpness != 1.0:
        result = ImageEnhance.Sharpness(result).enhance(sharpness)

    return result


def image_to_bytes(image, fmt):
    buffer = io.BytesIO()

    if fmt == "JPG":
        image.convert("RGB").save(
            buffer,
            format="JPEG",
            quality=95,
            optimize=True,
        )
    else:
        image.save(
            buffer,
            format="PNG",
            optimize=True,
        )

    return buffer.getvalue()


def image_data_url(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


def get_secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


# =========================================================
# EMAIL FEEDBACK
# =========================================================

def send_feedback(name, email, message):
    service_id = get_secret("EMAILJS_SERVICE_ID")
    template_id = get_secret("EMAILJS_TEMPLATE_ID")
    public_key = get_secret("EMAILJS_PUBLIC_KEY")

    if not all([service_id, template_id, public_key]):
        return (
            False,
            "لم يتم إعداد EmailJS بعد. أضف بياناته إلى Secrets في Streamlit Cloud.",
        )

    payload = {
        "service_id": service_id,
        "template_id": template_id,
        "user_id": public_key,
        "template_params": {
            "to_email": OWNER_EMAIL,
            "from_name": name or "زائر الموقع",
            "from_email": email or "غير متوفر",
            "message": message,
        },
    }

    try:
        response = requests.post(
            EMAILJS_URL,
            json=payload,
            timeout=20,
        )
    except requests.RequestException:
        return False, "تعذّر الاتصال بخدمة البريد. حاول لاحقًا."

    if response.status_code == 200:
        return True, "قبلت خدمة البريد إرسال رأيك. شكرًا لك! ❤️"

    return False, "فشل الإرسال. راجع إعدادات EmailJS وقالب البريد."


# =========================================================
# SIDEBAR SETTINGS
# =========================================================

with st.sidebar:
    st.header("⚙️ إعدادات الصورة")

    background_mode = st.selectbox(
        "الخلفية",
        BACKGROUND_OPTIONS,
    )

    custom_color = "#808080"

    if background_mode == CUSTOM_COLOR_MODE:
        custom_color = st.color_picker(
            "لون الخلفية",
            "#808080",
        )

    background_upload = None

    if background_mode == CUSTOM_IMAGE_MODE:
        bg_file = st.file_uploader(
            "ارفع صورة الخلفية",
            type=["png", "jpg", "jpeg", "webp"],
            key="background_upload",
        )

        if bg_file:
            background_upload = load_image(
                io.BytesIO(bg_file.getvalue())
            )

    st.divider()
    st.subheader("🔄 التدوير والتكبير")

    rotation = st.slider(
        "زاوية التدوير",
        0, 360, 0, 1,
    )

    zoom_level = st.slider(
        "التكبير — 8 مستويات",
        1, 8, 4, 1,
    )

    st.divider()
    st.subheader("💡 تحسين الصورة")

    brightness = st.slider(
        "الإضاءة",
        0.5, 1.8, 1.0, 0.05,
    )

    contrast = st.slider(
        "التباين",
        0.5, 1.8, 1.0, 0.05,
    )

    sharpness = st.slider(
        "الوضوح",
        0.5, 2.0, 1.0, 0.05,
    )

    st.caption(
        "تحسين عام للصورة؛ لا يُجري تعديلًا مقصودًا على ملامح الوجه."
    )


# =========================================================
# UPLOAD AND PROCESS
# =========================================================

uploaded_file = st.file_uploader(
    "📤 اختر صورة من جهازك أو هاتفك",
    type=["jpg", "jpeg", "png", "webp"],
    key="main_upload",
)

if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # عند تغيير الصورة نمسح نتائج الصورة السابقة.
    if st.session_state.get("active_file_hash") != file_hash:
        for key in (
            "original_result",
            "processed_result",
            "final_result",
            "cropped_result",
            "position_x",
            "position_y",
        ):
            st.session_state.pop(key, None)

        st.session_state["active_file_hash"] = file_hash
        st.session_state["position_x"] = 0.5
        st.session_state["position_y"] = 0.5

    original = limit_size(
        load_image(io.BytesIO(file_bytes))
    )

    st.subheader("الصورة الأصلية")
    st.image(original, use_container_width=True)

    process_clicked = st.button(
        "✂️ إزالة الخلفية وتجهيز الصورة",
        type="primary",
        use_container_width=True,
    )

    if process_clicked:
        if (
            background_mode == CUSTOM_IMAGE_MODE
            and background_upload is None
        ):
            st.error("ارفع صورة الخلفية أولًا.")
        else:
            try:
                with st.spinner(
                    "جارٍ إزالة الخلفية... قد تستغرق العملية بعض الوقت."
                ):
                    cutout = get_cutout(original, file_hash)

                st.session_state["original_result"] = original
                st.session_state["processed_file_hash"] = file_hash
                st.session_state.pop("cropped_result", None)

                st.success("تم تجهيز قصاصة الشخص.")

            except Exception as error:
                st.error(
                    "تعذّرت إزالة الخلفية. تحقق من الذاكرة والمكتبات."
                )
                st.caption(str(error))

    # لا نعرض أدوات التحرير قبل تجهيز قصاصة الشخص.
    if (
        st.session_state.get("processed_file_hash") == file_hash
        and "original_result" in st.session_state
    ):
        try:
            cutout = get_cutout(original, file_hash)

            background = make_background(
                original.size,
                background_mode,
                custom_color,
                background_upload,
            )

            subject = get_subject(
                cutout,
                rotation,
                zoom_level,
                original.size,
            )

            # -------------------------------------------------
            # POSITION CONTROLS
            # -------------------------------------------------

            st.divider()
            st.header("🎯 تحريك الشخص داخل الخلفية")
            st.write(
                "استخدم أشرطة التحكم أو اسحب الشخص مباشرة في المعاينة."
            )

            col_x, col_y = st.columns(2)

            with col_x:
                pos_x = st.slider(
                    "الموضع الأفقي",
                    0, 100,
                    int(st.session_state.get("position_x", 0.5) * 100),
                    key="horizontal_position",
                )

            with col_y:
                pos_y = st.slider(
                    "الموضع العمودي",
                    0, 100,
                    int(st.session_state.get("position_y", 0.5) * 100),
                    key="vertical_position",
                )

            # مزامنة أشرطة التحكم مع الحالة الحالية.
            if "drag_x" in st.session_state:
                pos_x = int(st.session_state["drag_x"] * 100)
                pos_y = int(st.session_state["drag_y"] * 100)

            st.session_state["position_x"] = pos_x / 100
            st.session_state["position_y"] = pos_y / 100

            # معاينة السحب المباشر تستخدم نفس أبعاد الصورة النهائية.
            display_w = min(760, original.width)
            display_h = max(
                1,
                int(display_w * original.height / original.width),
            )

            if display_h > 760:
                display_h = 760
                display_w = max(
                    1,
                    int(display_h * original.width / original.height),
                )

            preview_bg = background.resize(
                (display_w, display_h),
                Image.Resampling.LANCZOS,
            )

            subject_preview = subject.copy()
            subject_preview.thumbnail(
                (display_w, display_h),
                Image.Resampling.LANCZOS,
            )

            current_x = st.session_state["position_x"]
            current_y = st.session_state["position_y"]

            drag_value = drag_position(
                background=image_data_url(preview_bg),
                subject=image_data_url(subject_preview),
                width=display_w,
                height=display_h,
                subject_width=subject_preview.width,
                subject_height=subject_preview.height,
                x=current_x,
                y=current_y,
                key="direct_drag_component",
                default=None,
            )

            if isinstance(drag_value, dict):
                new_x = min(1.0, max(0.0, float(drag_value.get("x", current_x))))
                new_y = min(1.0, max(0.0, float(drag_value.get("y", current_y))))

                st.session_state["position_x"] = new_x
                st.session_state["position_y"] = new_y

                # إعادة تشغيل الصفحة لتحديث أشرطة التحكم والمعاينة.
                if (
                    abs(new_x - current_x) > 0.001
                    or abs(new_y - current_y) > 0.001
                ):
                    st.session_state["drag_x"] = new_x
                    st.session_state["drag_y"] = new_y
                    st.rerun()

            # -------------------------------------------------
            # COMPOSE FINAL RESULT
            # -------------------------------------------------

            final_result = compose_photo(
                background,
                subject,
                st.session_state["position_x"],
                st.session_state["position_y"],
            )

            final_result = improve_photo(
                final_result,
                brightness,
                contrast,
                sharpness,
            )

            # إذا تغيّرت الإعدادات، لا نحتفظ بقصّ قديم.
            signature = (
                background_mode,
                custom_color,
                rotation,
                zoom_level,
                brightness,
                contrast,
                sharpness,
                st.session_state["position_x"],
                st.session_state["position_y"],
                background_upload.size if background_upload else None,
            )

            if st.session_state.get("edit_signature") != signature:
                st.session_state["edit_signature"] = signature
                st.session_state.pop("cropped_result", None)

            st.session_state["processed_result"] = final_result

            # -------------------------------------------------
            # CROPPING
            # -------------------------------------------------

            st.divider()
            st.header("✂️ القصّ الدقيق")
            st.write(
                "حدد إطار القصّ بالفأرة أو بإصبعك، ثم طبّق القصّ "
                "أو ارجع إلى الصورة الكاملة."
            )

            try:
                cropped_preview = st_cropper(
                    final_result,
                    realtime_update=True,
                    box_color="#D4AF37",
                    aspect_ratio=None,
                    return_type="image",
                    should_resize_image=True,
                )

                crop_col, reset_col = st.columns(2)

                with crop_col:
                    if st.button(
                        "✅ تطبيق القصّ",
                        use_container_width=True,
                    ):
                        st.session_state["cropped_result"] = (
                            cropped_preview.convert("RGB")
                        )
                        st.rerun()

                with reset_col:
                    if st.button(
                        "↩️ التراجع عن القصّ",
                        use_container_width=True,
                    ):
                        st.session_state.pop("cropped_result", None)
                        st.rerun()

            except Exception as error:
                st.warning(
                    "أداة القصّ غير متاحة حاليًا. "
                    "تحقق من إصدار streamlit-cropper."
                )
                st.caption(str(error))

            # -------------------------------------------------
            # BEFORE / AFTER
            # -------------------------------------------------

            st.divider()
            st.header("🔍 مقارنة قبل وبعد")

            output_image = st.session_state.get(
                "cropped_result",
                final_result,
            )

            before_col, after_col = st.columns(2)

            with before_col:
                st.markdown("**قبل التعديل**")
                st.image(
                    st.session_state["original_result"],
                    use_container_width=True,
                )

            with after_col:
                st.markdown("**بعد التعديل**")
                st.image(
                    output_image,
                    use_container_width=True,
                )

            file_format = st.radio(
                "صيغة التنزيل",
                ["PNG", "JPG"],
                horizontal=True,
            )

            st.download_button(
                "⬇️ تحميل الصورة النهائية",
                data=image_to_bytes(output_image, file_format),
                file_name=(
                    "SEIF_PHOTO_STUDIO."
                    + file_format.lower()
                ),
                mime=(
                    "image/png"
                    if file_format == "PNG"
                    else "image/jpeg"
                ),
                use_container_width=True,
            )

        except Exception as error:
            st.error("حدث خطأ أثناء تجهيز الصورة النهائية.")
            st.caption(str(error))


# =========================================================
# FEEDBACK FORM
# =========================================================

st.divider()
st.header("💬 رأيك يهمّنا")
st.write("أرسل اقتراحك لتحسين SEIF PHOTO STUDIO PRO.")

with st.form("feedback_form", clear_on_submit=True):
    feedback_name = st.text_input(
        "اسمك (اختياري)",
        max_chars=100,
    )

    feedback_email = st.text_input(
        "بريدك الإلكتروني (اختياري)",
        max_chars=150,
    )

    feedback_message = st.text_area(
        "اكتب رأيك هنا",
        max_chars=3000,
        placeholder="اكتب رأيك أو اقتراحك...",
    )

    submitted = st.form_submit_button(
        "📨 إرسال الرأي",
        use_container_width=True,
    )

if submitted:
    name = feedback_name.strip()
    email = feedback_email.strip()
    message = feedback_message.strip()

    last_sent = st.session_state.get("last_feedback", 0)
    wait = FEEDBACK_COOLDOWN - (time.time() - last_sent)

    if not message:
        st.error("اكتب رأيك قبل الإرسال.")

    elif email and not EMAIL_RE.match(email):
        st.error("البريد الإلكتروني غير صحيح.")

    elif wait > 0:
        st.warning(
            f"يرجى الانتظار {int(wait)} ثانية قبل الإرسال مجددًا."
        )

    else:
        ok, response_message = send_feedback(
            name,
            email,
            message,
        )

        if ok:
            st.session_state["last_feedback"] = time.time()
            st.success(response_message)
        else:
            st.error(response_message)


# =========================================================
# STUDIO INFORMATION
# =========================================================

st.divider()
st.header("📍 معلومات الاستوديو")

st.link_button(
    "📍 موقع الاستوديو على Google Maps",
    MAPS_URL,
)

st.markdown(
    f"📞 الهاتف: [{PHONE}](tel:{PHONE_INTL})"
)

st.code(PHONE)

st.write(f"📧 البريد الإلكتروني: {OWNER_EMAIL}")
st.caption("SEIF PHOTO STUDIO PRO ©")
