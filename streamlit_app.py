from pathlib import Path

code = r'''import io
import json
import sqlite3
import zipfile
import base64
from io import BytesIO
from pathlib import Path
from datetime import datetime

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from rembg import new_session, remove

# =========================================================
# SEIF PHOTO STUDIO PRO — نسخة مطوّرة
# =========================================================
APP_DIR = Path(__file__).parent
BG_DIR = APP_DIR / "backgrounds"
DATA_DIR = APP_DIR / "studio_data"
DB_PATH = DATA_DIR / "history.sqlite3"
BG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="SEIF PHOTO STUDIO PRO",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
:root { color-scheme: dark; --bg:#101114; --panel:#1B1D22; --border:#343740; --gold:#D4AF37; --text:#F5F5F5; --muted:#B9BDC7; }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  font-family:'Cairo',sans-serif!important; background:var(--bg)!important; color:var(--text)!important;
}
.stApp { direction:rtl; }
[data-testid="stHeader"] { background:rgba(16,17,20,.96)!important; }
[data-testid="stSidebar"] { background:#17191E!important; border-left:1px solid var(--border); }
[data-testid="stSidebar"] * { color:var(--text); }
.stApp h1,.stApp h2,.stApp h3,.stApp p,.stApp label,[data-testid="stMarkdownContainer"] { color:var(--text); }
.hero {text-align:center;padding:22px 12px;margin:8px 0 22px;background:linear-gradient(135deg,#1B1D22,#252018);border:1px solid #6D5926;border-radius:20px;}
.hero h1 {color:var(--gold)!important;font-weight:800;margin-bottom:8px;}
.hero p {color:var(--muted)!important;margin:4px 0;}
.stButton>button,.stDownloadButton>button,.stLinkButton>a {border-radius:12px!important;font-weight:700!important;min-height:44px;}
.stButton>button[kind="primary"] {background:var(--gold)!important;color:#171717!important;border:1px solid var(--gold)!important;}
.stButton>button:not([kind="primary"]),.stDownloadButton>button,.stLinkButton>a {background:var(--panel)!important;color:var(--text)!important;border:1px solid var(--border)!important;}
.stButton>button:hover,.stDownloadButton>button:hover,.stLinkButton>a:hover {border-color:var(--gold)!important;}
[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stExpander"] {border-color:var(--border)!important;border-radius:14px!important;}
[data-testid="stFileUploader"] {background:#181A1F;border:1px dashed #6D5926;border-radius:14px;padding:10px;}
.stProgress>div>div>div {background-color:var(--gold)!important;}
.contact {text-align:center;padding:22px 10px;margin-top:35px;border-top:1px solid var(--border);color:var(--muted);}
.contact h3 {color:var(--gold)!important;}
img {border-radius:10px;}
@media(max-width:768px){.hero{padding:16px 8px}.hero h1{font-size:1.7rem}}
</style>
<div class="hero">
<h1>SEIF PHOTO STUDIO PRO 📸</h1>
<p>استوديو احترافي لمعالجة الصور وتغيير الخلفيات</p>
<p>قصّ ذكي • صور رسمية • إضاءة متوازنة • سجل المشاريع</p>
</div>
""", unsafe_allow_html=True)

MODELS = {
    "متوازن - u2net": "u2net",
    "دقة أعلى - isnet-general-use": "isnet-general-use",
    "خاص بالأشخاص - u2net_human_seg": "u2net_human_seg",
    "خفيف - silueta": "silueta",
}
COLORS = {
    "رمادي": "#808080", "أبيض": "#FFFFFF", "أزرق رسمي": "#2F6FD6",
    "أزرق فاتح": "#BFD9F5", "أحمر": "#C62828", "أخضر": "#2E7D32",
    "بيج": "#E8DCC8", "أسود": "#000000", "لون مخصص": None,
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
    "لون ثابت", "تدرج لوني", "صورة خلفية مخصصة",
    "خلفية من المكتبة المحلية", "تمويه الخلفية الأصلية", "شفاف PNG",
]
BG_CATEGORIES = {
    "الطبيعة": ["nature", "landscape", "forest", "mountains", "waterfall", "field", "lake", "flowers", "garden", "desert"],
    "المدن والهندسة": ["city", "city-street", "architecture", "old-town", "modern-building", "urban", "street", "bridge", "skyline", "plaza"],
    "البحر والسواحل": ["beach", "sea", "ocean", "coast", "tropical-beach", "blue-water", "rocky-coast", "sunset-sea", "harbor", "island"],
    "الأعراس والفخامة": ["wedding-hall", "luxury-interior", "golden-hall", "floral-decor", "elegant-room", "chandelier", "wedding-flowers", "classic-interior", "marble-hall", "luxury-decor"],
    "الحدائق والزهور": ["flower-garden", "roses", "botanical-garden", "tulips", "greenhouse", "spring-garden", "flower-field", "green-park", "japanese-garden", "orchard"],
    "تقليدي وتاريخي": ["historic-building", "medina", "traditional-house", "stone-arch", "old-door", "courtyard", "tunisian-architecture", "mosaic-wall", "historic-street", "traditional-decor"],
    "القصور والمباني": ["palace", "castle", "grand-staircase", "historic-palace", "courtyard-palace", "classic-building", "villa", "luxury-staircase", "museum-hall", "manor"],
    "خلفيات فنية": ["abstract-background", "neutral-texture", "studio-backdrop", "beige-texture", "gray-texture", "dark-texture", "gold-texture", "soft-gradient", "minimal-background", "bokeh-background"],
}

def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

def load_image(data, max_side=2000):
    with Image.open(BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    if max_side and max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
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

def refine_edges(subject, shrink=0, feather=0.5):
    # لا نقلّص القناع افتراضيًا حتى لا نحذف أطراف البدلة.
    alpha = subject.getchannel("A")
    if shrink > 0:
        alpha = alpha.filter(ImageFilter.MinFilter(shrink * 2 + 1))
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

def match_subject_lighting(subject, background, strength=0.35):
    """مطابقة تقريبية للسطوع العام؛ لا تغيّر ملامح الوجه عمدًا."""
    if strength <= 0:
        return subject
    bg = background.convert("RGB")
    subj_rgb = subject.convert("RGB")
    alpha = np.asarray(subject.getchannel("A"), dtype=np.float32) / 255.0
    srgb = np.asarray(subj_rgb, dtype=np.float32)
    brgb = np.asarray(bg, dtype=np.float32)
    if alpha.max() <= 0:
        return subject
    subject_luma = (0.299 * srgb[:, :, 0] + 0.587 * srgb[:, :, 1] + 0.114 * srgb[:, :, 2])
    background_luma = (0.299 * brgb[:, :, 0] + 0.587 * brgb[:, :, 1] + 0.114 * brgb[:, :, 2])
    valid = alpha > 0.65
    if not np.any(valid):
        return subject
    subject_mean = float(np.mean(subject_luma[valid]))
    bg_mean = float(np.mean(background_luma))
    if subject_mean < 1:
        return subject
    target = np.clip(bg_mean * 0.92, 45, 210)
    factor = 1.0 + (np.clip(target / subject_mean, 0.78, 1.22) - 1.0) * strength
    adjusted = np.clip(srgb * factor, 0, 255).astype(np.uint8)
    result = Image.fromarray(adjusted, "RGB").convert("RGBA")
    result.putalpha(subject.getchannel("A"))
    return result

def smart_crop_box(subject, ratio, pad, vertical_position=0.5):
    mask = subject.getchannel("A").point(lambda value: 255 if value > 20 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return (0, 0, subject.width, subject.height)
    left, top, right, bottom = bbox
    body_w, body_h = right - left, bottom - top
    crop_h = body_h * (1 + pad)
    crop_w = crop_h * ratio
    if crop_w < body_w * (1 + pad):
        crop_w = body_w * (1 + pad)
        crop_h = crop_w / ratio
    center_x = (left + right) / 2
    center_y = top + body_h * vertical_position
    x1, y1 = int(center_x - crop_w / 2), int(center_y - crop_h * vertical_position)
    return (x1, y1, int(x1 + crop_w), int(y1 + crop_h))

def make_gradient(size, color1, color2):
    width, height = size
    start, end = np.array(hex_to_rgb(color1), dtype=float), np.array(hex_to_rgb(color2), dtype=float)
    values = np.linspace(0, 1, height)[:, None, None]
    rows = start[None, None, :] * (1 - values) + end[None, None, :] * values
    array = np.broadcast_to(rows, (height, width, 3)).astype(np.uint8).copy()
    return Image.fromarray(array, "RGB").convert("RGBA")

def add_shadow(canvas, subject, opacity, blur, offset):
    alpha = subject.getchannel("A").point(lambda value: int(value * opacity))
    shadow = Image.new("RGBA", subject.size, (0, 0, 0, 255))
    shadow.putalpha(alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(shadow, (offset, offset))
    return Image.alpha_composite(canvas, layer)

def get_local_backgrounds():
    allowed = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted([p for p in BG_DIR.rglob("*") if p.is_file() and p.suffix.lower() in allowed])

def build_background(size, cfg, original):
    mode = cfg["bg_mode"]
    if mode == "لون ثابت":
        return Image.new("RGBA", size, (*hex_to_rgb(cfg["color"]), 255))
    if mode == "تدرج لوني":
        return make_gradient(size, cfg["grad1"], cfg["grad2"])
    if mode in ("صورة خلفية مخصصة", "خلفية من المكتبة المحلية"):
        bg_bytes = cfg.get("bg_bytes")
        if bg_bytes:
            with Image.open(BytesIO(bg_bytes)) as source:
                background = ImageOps.exif_transpose(source).convert("RGBA")
            return ImageOps.fit(background, size, method=Image.Resampling.LANCZOS)
        return Image.new("RGBA", size, (128, 128, 128, 255))
    if mode == "تمويه الخلفية الأصلية":
        background = ImageOps.fit(original, size, method=Image.Resampling.LANCZOS)
        return background.filter(ImageFilter.GaussianBlur(cfg["blur"])).convert("RGBA")
    if mode == "شفاف PNG":
        return Image.new("RGBA", size, (0, 0, 0, 0))
    return Image.new("RGBA", size, (128, 128, 128, 255))

def compose(original, subject, cfg):
    subject = refine_edges(subject, cfg["shrink"], cfg["feather"])
    subject = adjust_subject(subject, cfg["brightness"], cfg["contrast"], cfg["saturation"])
    ratio, target_size = CROPS[cfg["crop"]]
    if ratio:
        box = smart_crop_box(subject, ratio, cfg["pad"], cfg["vertical_position"])
        subject, original = subject.crop(box), original.crop(box)
        if target_size:
            subject = subject.resize(target_size, Image.Resampling.LANCZOS)
            original = original.resize(target_size, Image.Resampling.LANCZOS)
    canvas = build_background(subject.size, cfg, original)
    if cfg["match_lighting"] and cfg["bg_mode"] != "شفاف PNG":
        subject = match_subject_lighting(subject, canvas, cfg["lighting_strength"])
    if cfg["shadow"] and cfg["bg_mode"] != "شفاف PNG":
        canvas = add_shadow(canvas, subject, cfg["shadow_opacity"], cfg["shadow_blur"], cfg["shadow_offset"])
    return Image.alpha_composite(canvas, subject)

def encode(image, fmt, quality):
    buffer = BytesIO()
    if fmt == "PNG":
        image.save(buffer, "PNG", dpi=(300, 300))
        return buffer.getvalue(), "image/png", "png"
    if fmt == "WEBP":
        image.convert("RGB").save(buffer, "WEBP", quality=quality)
        return buffer.getvalue(), "image/webp", "webp"
    image.convert("RGB").save(buffer, "JPEG", quality=quality, subsampling=0, optimize=True, dpi=(300, 300))
    return buffer.getvalue(), "image/jpeg", "jpg"

def make_sheet(image, sheet_px=(1200, 1800), gap=20):
    sheet_w, sheet_h = sheet_px
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    white.alpha_composite(image.convert("RGBA"))
    photo = white.convert("RGB")
    photo.thumbnail((sheet_w - 2 * gap, sheet_h - 2 * gap), Image.Resampling.LANCZOS)
    photo_w, photo_h = photo.size
    cols = max(1, (sheet_w - gap) // (photo_w + gap))
    rows = max(1, (sheet_h - gap) // (photo_h + gap))
    while cols > 1 and cols * photo_w + (cols + 1) * gap > sheet_w:
        cols -= 1
    while rows > 1 and rows * photo_h + (rows + 1) * gap > sheet_h:
        rows -= 1
    sheet = Image.new("RGB", sheet_px, "white")
    total_w, total_h = cols * photo_w + (cols - 1) * gap, rows * photo_h + (rows - 1) * gap
    start_x, start_y = (sheet_w - total_w) // 2, (sheet_h - total_h) // 2
    for row in range(rows):
        for col in range(cols):
            sheet.paste(photo, (start_x + col * (photo_w + gap), start_y + row * (photo_h + gap)))
    return sheet

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            before_data BLOB NOT NULL,
            after_data BLOB NOT NULL,
            settings TEXT NOT NULL
        )""")
        con.commit()

def image_bytes(image, fmt="PNG"):
    buf = BytesIO()
    if fmt.upper() == "JPEG":
        image.convert("RGB").save(buf, "JPEG", quality=95, optimize=True)
    else:
        image.save(buf, "PNG")
    return buf.getvalue()

def save_project(name, before_image, after_image, settings):
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO projects(created_at,name,before_data,after_data,settings) VALUES(?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name,
             sqlite3.Binary(image_bytes(before_image)), sqlite3.Binary(image_bytes(after_image)),
             json.dumps(settings, ensure_ascii=False, default=str))
        )
        con.commit()

def load_projects():
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        return con.execute("SELECT id,created_at,name,settings FROM projects ORDER BY id DESC").fetchall()

def load_project_images(project_id):
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute("SELECT before_data,after_data FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        return None, None
    return Image.open(BytesIO(row[0])).convert("RGBA"), Image.open(BytesIO(row[1])).convert("RGBA")

def delete_project(project_id):
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM projects WHERE id=?", (project_id,))
        con.commit()

def render_comparison(before_image, after_image, height=520):
    # تفاعل السحب يعمل داخل المكوّن نفسه، والصورتان معروضتان بمحاذاة واحدة.
    before = base64.b64encode(image_bytes(before_image)).decode("ascii")
    after = base64.b64encode(image_bytes(after_image)).decode("ascii")
    html = f"""
    <div id="compare-wrap" style="direction:ltr;position:relative;width:100%;max-width:100%;height:{height}px;overflow:hidden;border-radius:12px;background:#222;touch-action:pan-y;user-select:none;">
      <img src="data:image/png;base64,{before}" style="position:absolute;width:100%;height:100%;object-fit:contain;inset:0;">
      <div id="after-clip" style="position:absolute;inset:0;width:50%;overflow:hidden;border-right:3px solid #D4AF37;box-sizing:border-box;">
        <img src="data:image/png;base64,{after}" style="position:absolute;max-width:none;width:100%;height:100%;object-fit:contain;inset:0;">
      </div>
      <div id="slider-handle" role="slider" aria-label="مقارنة قبل وبعد" tabindex="0" style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:42px;height:42px;border:2px solid #D4AF37;border-radius:50%;background:#171717;color:#fff;display:flex;align-items:center;justify-content:center;font:700 18px sans-serif;box-shadow:0 2px 12px #0008;cursor:ew-resize;">↔</div>
      <div style="position:absolute;top:10px;left:10px;background:#111c;color:#fff;padding:5px 9px;border-radius:8px;font:600 13px sans-serif;">قبل</div>
      <div style="position:absolute;top:10px;right:10px;background:#111c;color:#fff;padding:5px 9px;border-radius:8px;font:600 13px sans-serif;">بعد</div>
    </div>
    <script>
    const wrap=document.getElementById('compare-wrap');
    const clip=document.getElementById('after-clip');
    const handle=document.getElementById('slider-handle');
    function setPos(clientX) {{
      const r=wrap.getBoundingClientRect();
      let pct=Math.max(0,Math.min(100,(clientX-r.left)/r.width*100));
      clip.style.width=pct+'%'; handle.style.left=pct+'%';
    }}
    let dragging=false;
    wrap.addEventListener('pointerdown',e=>{{dragging=true;wrap.setPointerCapture(e.pointerId);setPos(e.clientX);}});
    wrap.addEventListener('pointermove',e=>{{if(dragging)setPos(e.clientX);}});
    wrap.addEventListener('pointerup',()=>dragging=false);
    wrap.addEventListener('pointercancel',()=>dragging=false);
    handle.addEventListener('keydown',e=>{{
      if(e.key==='ArrowLeft'){{e.preventDefault();setPos(wrap.getBoundingClientRect().left+Math.max(0,parseFloat(clip.style.width||'50')-3)/100*wrap.getBoundingClientRect().width);}}
      if(e.key==='ArrowRight'){{e.preventDefault();setPos(wrap.getBoundingClientRect().left+Math.min(100,parseFloat(clip.style.width||'50')+3)/100*wrap.getBoundingClientRect().width);}}
    }});
    </script>
    """
    components.html(html, height=height + 10, scrolling=False)

# =========================================================
# إعدادات بسيطة: الأدوات الأساسية ظاهرة والمتقدمة مطوية
# =========================================================
cfg = {}
with st.sidebar:
    st.markdown("## ⚙️ إعدادات الاستوديو")
    with st.expander("🎨 الخلفية", expanded=True):
        cfg["bg_mode"] = st.selectbox("نوع الخلفية", BG_MODES)
        cfg.update({"color":"#808080","grad1":"#FFFFFF","grad2":"#808080","bg_bytes":None,"blur":25})
        if cfg["bg_mode"] == "لون ثابت":
            color_name = st.selectbox("لون الخلفية", list(COLORS))
            cfg["color"] = st.color_picker("لون مخصص", "#808080") if COLORS[color_name] is None else COLORS[color_name]
        elif cfg["bg_mode"] == "تدرج لوني":
            c1,c2=st.columns(2)
            cfg["grad1"]=c1.color_picker("اللون الأول","#FFFFFF")
            cfg["grad2"]=c2.color_picker("اللون الثاني","#808080")
        elif cfg["bg_mode"] == "صورة خلفية مخصصة":
            bg_file=st.file_uploader("ارفع الخلفية",type=["jpg","jpeg","png","webp"],key="custom_bg")
            cfg["bg_bytes"]=bg_file.getvalue() if bg_file else None
        elif cfg["bg_mode"] == "خلفية من المكتبة المحلية":
            backgrounds=get_local_backgrounds()
            if backgrounds:
                categories=["كل الخلفيات"] + sorted({p.parent.name for p in backgrounds if p.parent != BG_DIR})
                category=st.selectbox("التصنيف",categories)
                shown=[p for p in backgrounds if category=="كل الخلفيات" or p.parent.name==category]
                names=[p.relative_to(BG_DIR).as_posix() for p in shown]
                chosen=st.selectbox("اختر خلفية",names)
                selected_path=BG_DIR / chosen
                cfg["bg_bytes"]=selected_path.read_bytes()
                st.image(cfg["bg_bytes"],caption=chosen,use_container_width=True)
            else:
                st.warning("مجلد backgrounds فارغ. أضف الصور داخله، ويمكنك إنشاء مجلد لكل تصنيف.")
                st.caption("لا تُضمّن هذه النسخة 80 صورة فعلية تلقائيًا؛ يجب وضع ملفات الصور في المجلد.")
        elif cfg["bg_mode"] == "تمويه الخلفية الأصلية":
            cfg["blur"]=st.slider("قوة التمويه",5,80,25)

    with st.expander("✨ الإضاءة والألوان", expanded=True):
        cfg["match_lighting"]=st.checkbox("مطابقة إضاءة الشخص مع الخلفية",value=True)
        cfg["lighting_strength"]=st.slider("قوة المطابقة",0.0,1.0,0.35,0.05)
        cfg["brightness"]=st.slider("سطوع الشخص",0.5,1.5,1.0,0.05)
        cfg["contrast"]=st.slider("تباين الشخص",0.5,1.5,1.0,0.05)
        cfg["saturation"]=st.slider("تشبع الألوان",0.0,2.0,1.0,0.05)
        cfg["shadow"]=st.checkbox("إضافة ظل ناعم",value=False)
        cfg["shadow_opacity"],cfg["shadow_blur"],cfg["shadow_offset"]=0.4,20,15
        if cfg["shadow"]:
            cfg["shadow_opacity"]=st.slider("قوة الظل",0.1,1.0,0.4,0.05)
            cfg["shadow_blur"]=st.slider("نعومة الظل",2,60,20)
            cfg["shadow_offset"]=st.slider("إزاحة الظل",0,60,15)

    with st.expander("✂️ المقاس والقص"):
        cfg["crop"]=st.selectbox("مقاس الصورة",list(CROPS))
        cfg["pad"]=st.slider("المساحة حول الشخص",0.0,0.8,0.2,0.05)
        cfg["vertical_position"]=st.slider("موضع القص رأسيًا",0.0,1.0,0.5,0.05)
        cfg["shrink"]=st.slider("تقليل الهالة (قد يقص الملابس)",0,5,0)
        cfg["feather"]=st.slider("تنعيم الحواف",0.0,5.0,0.5,0.5)
        cfg["matting"]=st.checkbox("تحسين حواف الشعر (أبطأ)",value=False)
        cfg["fg_thr"],cfg["bg_thr"],cfg["erode"]=240,10,0
        if cfg["matting"]:
            cfg["fg_thr"]=st.slider("عتبة المقدمة",150,255,240)
            cfg["bg_thr"]=st.slider("عتبة الخلفية",0,100,10)
            cfg["erode"]=st.slider("حجم تحسين الحواف",0,40,0)
        cfg["model_label"]=st.selectbox("نموذج القص",list(MODELS),index=1)
        cfg["model"]=MODELS[cfg["model_label"]]
        cfg["max_side"]=st.select_slider("أقصى حجم للصورة",[1024,1600,2000,3000,4000],value=2000)

    with st.expander("💾 التصدير"):
        out_fmt=st.radio("صيغة الصورة",["JPEG","PNG","WEBP"],horizontal=True)
        quality=st.slider("جودة الصورة",60,100,95) if out_fmt!="PNG" else 95
        if cfg["bg_mode"]=="شفاف PNG":
            out_fmt="PNG"
            st.caption("سيتم التصدير بصيغة PNG للحفاظ على الشفافية.")

main_tab, history_tab, library_tab = st.tabs(["🪄 تعديل الصور", "🗂️ السجل", "🖼️ مكتبة الخلفيات"])

with main_tab:
    photos=st.file_uploader("📤 ارفع صورة أو عدة صور",type=["jpg","jpeg","png","webp"],accept_multiple_files=True)
    if photos:
        with st.expander(f"معاينة الصور المرفوعة ({len(photos)})"):
            preview_cols=st.columns(min(len(photos),5))
            for i,photo in enumerate(photos):
                preview_cols[i % len(preview_cols)].image(photo,caption=photo.name,use_container_width=True)

    run=st.button("🪄 معالجة الصور",type="primary",disabled=not photos,use_container_width=True)
    if run and photos:
        results=[]
        progress=st.progress(0.0,text="جارٍ تجهيز الصور...")
        for index,photo in enumerate(photos):
            try:
                original,subject=cut_subject(
                    photo.getvalue(),cfg["model"],cfg["matting"],cfg["fg_thr"],cfg["bg_thr"],cfg["erode"],cfg["max_side"]
                )
                final_image=compose(original.copy(),subject.copy(),cfg)
                data,mime,extension=encode(final_image,out_fmt,quality)
                base_name=Path(photo.name).stem
                item={"name":f"{base_name}-seif.{extension}","mime":mime,"data":data,"before":original,"after":final_image}
                if CROPS[cfg["crop"]][1]:
                    item["sheet"]=encode(make_sheet(final_image),"JPEG",95)[0]
                results.append(item)
                # حفظ تلقائي في السجل على القرص المحلي/المثبّت للتطبيق
                save_project(item["name"],original,final_image,{k:v for k,v in cfg.items() if k not in ("bg_bytes",)})
            except Exception as error:
                st.error(f"تعذّرت معالجة {photo.name}: {error}")
            progress.progress((index+1)/len(photos),text=f"معالجة الصورة {index+1} من {len(photos)}")
        progress.empty()
        st.session_state["results"]=results

    results=st.session_state.get("results",[])
    if results:
        st.success(f"اكتملت معالجة {len(results)} صورة. حُفظت النتائج في السجل إذا كان التخزين الدائم متاحًا.")
        for i,result in enumerate(results):
            st.markdown(f"### 📷 {result['name']}")
            st.caption("اسحب الخط الذهبي يمينًا ويسارًا لمقارنة قبل وبعد.")
            render_comparison(result["before"],result["after"])
            with st.expander("عرض الصورتين منفصلتين"):
                c1,c2=st.columns(2)
                c1.image(result["before"],caption="قبل",use_container_width=True)
                c2.image(result["after"],caption="بعد",use_container_width=True)
            d1,d2=st.columns(2)
            d1.download_button("⬇️ تنزيل الصورة",result["data"],file_name=result["name"],mime=result["mime"],key=f"download_{i}",use_container_width=True)
            if "sheet" in result:
                d2.download_button("🖨️ تنزيل ورقة الطباعة",result["sheet"],file_name=f"sheet-{i+1}.jpg",mime="image/jpeg",key=f"sheet_{i}",use_container_width=True)
            st.divider()
        if len(results)>1:
            zip_buffer=BytesIO()
            with zipfile.ZipFile(zip_buffer,"w",zipfile.ZIP_DEFLATED) as archive:
                for result in results:
                    archive.writestr(result["name"],result["data"])
            st.download_button("📦 تنزيل كل الصور ZIP",zip_buffer.getvalue(),file_name="seif-photos.zip",mime="application/zip",use_container_width=True)
    elif not photos:
        st.info("ارفع صورة، ثم اختر الخلفية والمقاس من الإعدادات.")

with history_tab:
    st.markdown("## 🗂️ سجل المشاريع المحفوظة")
    st.caption("تُحفظ نسخ الصورة الأصلية والنتيجة في قاعدة بيانات SQLite بجانب التطبيق. في الاستضافة السحابية قد يُمسح التخزين المحلي عند إعادة نشر التطبيق ما لم تُستخدم مساحة تخزين دائمة.")
    projects=load_projects()
    if not projects:
        st.info("لا توجد مشاريع محفوظة حتى الآن. عالج صورة أولًا.")
    else:
        for project_id,created_at,name,settings in projects:
            with st.expander(f"{created_at} — {name}"):
                before_img,after_img=load_project_images(project_id)
                if before_img and after_img:
                    render_comparison(before_img,after_img,height=420)
                    a,b=st.columns(2)
                    a.download_button("تنزيل الأصل",image_bytes(before_img),file_name=f"original-{project_id}.png",mime="image/png",key=f"hist_before_{project_id}",use_container_width=True)
                    b.download_button("تنزيل النتيجة",image_bytes(after_img),file_name=f"result-{project_id}.png",mime="image/png",key=f"hist_after_{project_id}",use_container_width=True)
                if st.button("🗑️ حذف هذا المشروع من السجل",key=f"delete_{project_id}"):
                    delete_project(project_id)
                    st.rerun()

with library_tab:
    st.markdown("## 🖼️ مكتبة الخلفيات المحلية")
    st.write("ضع ملفات الصور داخل مجلد `backgrounds` بجانب `streamlit_app.py`. أنشئ مجلدات فرعية للتصنيفات مثل `Nature` و`Cities` و`Wedding`؛ ستظهر أسماء المجلدات كتصنيفات.")
    st.warning("هذه النسخة تحتوي على نظام المكتبة، لكنها لا تحتوي تلقائيًا على 80 ملف صورة. يجب إضافة الصور الفعلية إلى مجلد backgrounds. استخدم صورًا تملك حق استخدامها.")
    library_files=get_local_backgrounds()
    st.write(f"عدد الخلفيات المكتشفة: **{len(library_files)}**")
    uploaded_backgrounds=st.file_uploader("أضف صورًا إلى المكتبة",type=["jpg","jpeg","png","webp"],accept_multiple_files=True,key="library_upload")
    if uploaded_backgrounds and st.button("حفظ الصور المرفوعة في مكتبة الخلفيات"):
        for bg in uploaded_backgrounds:
            safe_name=Path(bg.name).name
            (BG_DIR/safe_name).write_bytes(bg.getvalue())
        st.success("حُفظت الصور في مجلد المكتبة لهذه البيئة.")
        st.rerun()
    if library_files:
        cols=st.columns(4)
        for i,path in enumerate(library_files):
            try:
                cols[i%4].image(str(path),caption=path.relative_to(BG_DIR).as_posix(),use_container_width=True)
            except Exception:
                pass

st.markdown("""
<div class="contact">
<h3>SEIF PHOTO STUDIO PRO 📸</h3>
<p>📍 القلعة الكبرى، سوسة، تونس</p>
<p>📞 97262953</p>
<p>تصوير • صور رسمية • معالجة الصور • تغيير الخلفيات</p>
</div>
""",unsafe_allow_html=True)
st.link_button("📍 افتح موقع الاستوديو على Google Maps","https://www.google.com/maps/search/?api=1&query=VG9M%2BPVX%2C+Rue+Taher+Sfar%2C+Kala%C3%A2+Kebira",use_container_width=True)
st.link_button("📞 الاتصال بالاستوديو","tel:97262953",use_container_width=True)
'''
path = Path("/mnt/data/streamlit_app.py")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(code, encoding="utf-8")
path.write_text(code, encoding="utf-8")
print(f"Created {path} ({len(code.splitlines())} lines)")
