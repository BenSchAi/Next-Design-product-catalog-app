import streamlit as st
import base64
import json
import pandas as pd
import io
import re
import urllib.parse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import constants

# =============================================================================
# CONSTANTS
# =============================================================================

FOLDER_ID_EXCELS = "1x7bE0YmGhrK_-0f06ixwlOKqquV_8AHZ"
FOLDER_ID_IMAGES = "1R4nm5cf2NEWB30IceF4cL5oShNlqurPS"

PRODUCTS_PER_PAGE = 12
COLUMNS_PER_ROW   = 4

COLOR_PRIMARY        = "#1E3A8A"
COLOR_SIDEBAR_BORDER = "#BFDBFE"
COLOR_TEXT_DARK      = "#334155"
COLOR_PRICE          = "#27ae60"
COLOR_PRICE_ILS      = "#7C3AED"
COLOR_DELIVERY       = "#444"
COLOR_PACKING        = "#666"
COLOR_OTHER          = "#888"
COLOR_GENERAL        = "#222"
COLOR_SAMPLE         = "#d35400"
COLOR_SOURCE         = "#999"
COLOR_MOQ_OK         = "#f1c40f"
COLOR_MOQ_NAN        = "#e74c3c"
COLOR_TAG_BG         = "#333"
COLOR_CAPACITY_BG    = "#eee"
COLOR_CAPACITY_TEXT  = "#333"
COLOR_SUCCESS        = "#219653"
COLOR_SOURCER_BG     = "#e0e7ff"
COLOR_SOURCER_TEXT   = "#3730a3"

FONT_MAIN = "'Arial', sans-serif"

CARD_HEIGHT         = "780px"
CARD_IMAGE_HEIGHT   = "220px"
CARD_DETAILS_HEIGHT = "280px"

DEFAULT_USD_ILS = 3.65

CATEGORY_MAP = {
    "טכנולוגיה וגאדג'טים": ["usb", "power bank", "speaker", "charger", "cable", "wireless",
                              "mouse", "earphone", "headphone", "bluetooth", "smart", "hub", "adapter"],
    "מחנאות, נופש וספורט": ["camp", "tent", "outdoor", "sport", "yoga", "fitness", "picnic",
                              "beach", "towel", "mat", "flashlight", "jump rope", "bottle",
                              "flask", "tumbler", "drinkware", "cooler"],
    "בקבוקים, כוסות ושתייה": ["bottle", "mug", "cup", "tumbler", "flask", "drinkware",
                                "thermos", "shaker", "glass", "straw"],
    "עטים וכלי כתיבה": ["pen", "pencil", "notebook", "notepad", "stylus", "marker",
                          "highlighter", "stationery", "diary"],
    "תיקים וארנקים": ["bag", "backpack", "tote", "pouch", "wallet", "drawstring",
                       "duffel", "briefcase", "cooler", "luggage"],
    "טקסטיל וביגוד": ["shirt", "t-shirt", "cap", "hat", "jacket", "apron", "socks",
                       "apparel", "wear"],
    "לבית ולמשרד": ["clock", "desk", "organizer", "frame", "lamp", "light", "home",
                     "office", "mouse pad", "lanyard", "keychain"],
    "עונות (קיץ/חורף)": ["summer", "winter", "umbrella", "fan", "sunglasses", "ice",
                           "warm", "blanket", "beanie", "scarf"],
    "אקולוגי וקיימות": ["eco", "bamboo", "wheat", "recycled", "cork", "sustainable",
                          "rpet", "organic", "cotton", "biodegradable"],
}

PACKING_KEYWORDS  = ['OPP BAG', 'POLY BAG', 'PE BAG', 'PACKING', 'MEAS', 'CTN', 'G.W', 'N.W', 'BOX']
PRICE_KEYWORDS    = ['USD', 'PRICE']
PACKING_KEYS      = ['PACKING', 'OPP', 'BOX', 'CTN', 'MEAS', 'G.W', 'N.W', 'KGS']
DELIVERY_KEYS     = ['DELIVERY', 'DAYS', 'LEAD TIME', 'VALIDITY']
GENERAL_KEYS      = ['DATE', 'SOURCER']  # ITEM ו-DESCRIPTION מוצגים ככותרת בלבד
SKIP_CONTENT_KEYS = ['WEB', 'HTTP', 'HTTPS', 'EXCHANGE RATE', 'FOB', 'PICTURE', 'PRODUCT DETAILS']
ITEM_TRIGGER_KEYS = ['ITEM NO', 'ITEM REF', 'ITEM:', '*ITEM', 'DESCRIPTION:', 'DESCRIPTION :']


# =============================================================================
# PAGE SETUP
# =============================================================================

st.set_page_config(
    page_title="Next Design - קטלוג חכם",
    layout="wide",
    initial_sidebar_state="expanded",
)

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'last_filters' not in st.session_state:
    st.session_state.last_filters = None


# =============================================================================
# CSS
# =============================================================================

st.markdown(f"""
<style>
:root {{{{ --font-serif: Arial, sans-serif; --font-sans: Arial, sans-serif; }}
html, body, [data-testid="stSidebar"], [data-testid="stSidebar"] *,
section[data-testid="stSidebar"], section[data-testid="stSidebar"] *,
.stText, p, h1, h2, h3, h4, h5, h6 {{{{
    font-family: Arial, sans-serif !important;
    font-style: normal !important;
}}
.material-icons, .stIcon, svg, i {{ font-family: "Material Icons" !important; }}
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header {{ background-color: transparent !important; }}
[data-testid="stSidebarHeader"] {{ display: none !important; }}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.5rem !important; padding-bottom: 2rem !important; }}
section[data-testid="stSidebar"] label p {{ font-family: Arial, sans-serif !important; color: {COLOR_TEXT_DARK} !important; font-weight: 700 !important; font-size: 15px !important; text-align: right !important; direction: rtl !important; width: 100%; }}
[data-testid="stWidgetLabel"] p {{ direction: rtl !important; text-align: right !important; font-family: Arial, sans-serif !important; }}
section[data-testid="stSidebar"] .stSlider > label, section[data-testid="stSidebar"] .stNumberInput > label {{ text-align: right !important; direction: rtl !important; display: block !important; width: 100% !important; font-family: Arial, sans-serif !important; }}
section[data-testid="stSidebar"] .stSlider input[type="range"], section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {{ direction: ltr !important; }}
section[data-testid="stSidebar"] .stNumberInput input {{ direction: ltr !important; text-align: left !important; }}
.stMultiSelect {{ position: relative !important; width: 100% !important; max-width: 100% !important; }}
.stMultiSelect [data-baseweb="popover"] {{ position: absolute !important; left: 0 !important; right: auto !important; width: fit-content !important; max-width: 280px !important; min-width: 200px !important; overflow: hidden !important; white-space: normal !important; word-break: break-word !important; box-sizing: border-box !important; z-index: 9999 !important; }}
[data-testid="stVirtualDropdown"] {{ position: absolute !important; left: 0 !important; right: auto !important; max-width: 280px !important; overflow: hidden !important; }}
.stMultiSelect div[data-baseweb="select"] {{ max-width: 100% !important; direction: rtl !important; width: 100% !important; position: relative !important; overflow: visible !important; }}
.stMultiSelect [data-baseweb="select"] [role="option"] {{ word-wrap: break-word !important; white-space: normal !important; }}
.stSelectbox div[data-baseweb="select"] {{ width: 100% !important; position: relative !important; }}
.stSelectbox [data-baseweb="popover"] {{ position: absolute !important; left: 0 !important; right: auto !important; max-width: 280px !important; overflow: hidden !important; }}
.stTextInput > div > div > input {{ font-family: Arial, sans-serif !important; border-radius: 30px !important; border: 2px solid #eaeaea !important; padding: 15px 20px !important; font-size: 16px !important; box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important; text-align: left !important; direction: ltr !important; }}
.stTextInput > div > div > input:focus {{ border-color: #111 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important; }}
div[data-testid="stVerticalBlock"] > div[style*="border"] {{ border-radius: 12px !important; border: 1px solid #f0f0f0 !important; box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important; background-color: white !important; padding: 12px !important; direction: ltr !important; text-align: left !important; height: 680px !important; min-height: 680px !important; max-height: 680px !important; display: flex !important; flex-direction: column !important; overflow: hidden !important; }}
div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {{ box-shadow: 0 10px 20px rgba(0,0,0,0.08) !important; }}
div[data-testid="stVerticalBlock"] > div[style*="border"] > div[data-testid="stVerticalBlock"] {{ height: 100% !important; max-height: 100% !important; overflow: hidden !important; display: flex !important; flex-direction: column !important; flex: 1 1 auto !important; min-height: 0 !important; }}
.img-box {{ width: 100%; height: 220px !important; min-height: 220px !important; max-height: 220px !important; flex-shrink: 0 !important; overflow: hidden; border-radius: 8px; background: #fafafa; display: flex; align-items: center; justify-content: center; position: relative; z-index: 1; margin-bottom: 6px; }}
.img-box img {{ max-width: 100%; max-height: 220px; object-fit: contain; border-radius: 4px; transition: none; position: relative; z-index: 1; cursor: zoom-in; }}
#img-zoom-overlay {{ display:none; position:fixed; z-index:999999; pointer-events:none; border-radius:12px; box-shadow:0 20px 60px rgba(0,0,0,0.45); border:2px solid rgba(255,255,255,0.6); transition: opacity 0.18s ease; opacity:0; background:#fff; }}
#img-zoom-overlay.visible {{ display:block; opacity:1; }}
#img-zoom-overlay img {{ width:100%; height:100%; object-fit:contain; border-radius:10px; display:block; }}
.card-details {{ flex-grow: 1 !important; overflow-y: auto !important; overflow-x: hidden !important; min-height: 0 !important; text-align: left; line-height: 1.55; padding-right: 3px; direction: ltr; font-size: 13px; }}
.card-footer {{ flex-shrink: 0 !important; margin-top: 6px; border-top: 1px solid #eee; padding-top: 6px; text-align: left; direction: ltr; }}
.email-btn {{ display: block; width: 100%; text-align: center; background-color: {COLOR_PRICE}; color: white !important; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 20px; transition: background-color 0.3s; font-family: Arial, sans-serif !important; }}
.email-btn:hover {{ background-color: {COLOR_SUCCESS}; }}
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 10px; }}
::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 10px; }}
::-webkit-scrollbar-thumb:hover {{ background: #999; }}
html, body {{ overflow-x: hidden !important; max-width: 100vw !important; }}
.main, .block-container {{ overflow-x: hidden !important; max-width: 100% !important; }}
main {{ overflow-x: hidden !important; max-width: 100vw !important; }}
* {{ max-width: 100% !important; box-sizing: border-box !important; }}
</style>
""", unsafe_allow_html=True)

import streamlit.components.v1 as components
components.html("""
<script>
(function() {
  var doc = window.parent.document;
  var overlay = doc.getElementById('img-zoom-overlay');
  if (!overlay) {
    overlay = doc.createElement('div');
    overlay.id = 'img-zoom-overlay';
    overlay.innerHTML = '<img src="" alt="zoom" style="width:100%;height:100%;object-fit:contain;border-radius:10px;display:block;"/>';
    overlay.style.cssText = 'display:none;position:fixed;z-index:999999;pointer-events:none;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,0.45);border:2px solid rgba(255,255,255,0.7);background:#fff;transition:opacity 0.18s ease;opacity:0;';
    doc.body.appendChild(overlay);
  }
  var overlayImg = overlay.querySelector('img');
  var ZOOM_SIZE = 380;
  var MARGIN = 16;
  var hideTimer = null;
  function showOverlay(src, rect) {
    clearTimeout(hideTimer);
    overlayImg.src = src;
    var left = rect.right + MARGIN;
    var top  = rect.top + (rect.height / 2) - (ZOOM_SIZE / 2);
    if (left + ZOOM_SIZE > window.parent.innerWidth - MARGIN) { left = rect.left - ZOOM_SIZE - MARGIN; }
    if (left < MARGIN) left = MARGIN;
    if (top < MARGIN) top = MARGIN;
    if (top + ZOOM_SIZE > window.parent.innerHeight - MARGIN) { top = window.parent.innerHeight - ZOOM_SIZE - MARGIN; }
    overlay.style.width   = ZOOM_SIZE + 'px';
    overlay.style.height  = ZOOM_SIZE + 'px';
    overlay.style.left    = left + 'px';
    overlay.style.top     = top  + 'px';
    overlay.style.display = 'block';
    requestAnimationFrame(function() { overlay.style.opacity = '1'; });
  }
  function hideOverlay() {
    overlay.style.opacity = '0';
    hideTimer = setTimeout(function() { overlay.style.display = 'none'; }, 180);
  }
  doc.addEventListener('mouseover', function(e) {
    var img = e.target.closest ? e.target.closest('.img-box img') : null;
    if (!img || !img.src || img.src.startsWith('data:,')) return;
    var rect = img.getBoundingClientRect();
    showOverlay(img.src, rect);
  });
  doc.addEventListener('mouseout', function(e) {
    var img = e.target.closest ? e.target.closest('.img-box img') : null;
    if (!img) return;
    hideOverlay();
  });
})();
</script>
""", height=0)


# =============================================================================
# DATA PROCESSING UTILITIES
# =============================================================================

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def format_moq_display(val):
    if val is None or pd.isna(val):
        return "NAN"
    try:
        num = float(val)
        return f"{num/1000:g}K" if num >= 1000 else f"{num:g}"
    except:
        return "NAN"


def extract_moq(details_list):
    for detail in details_list:
        d_up = detail.upper()
        if 'MOQ' in d_up:
            clean_d = d_up.replace(',', '')
            match = re.search(r'MOQ.*?(\d+\.?\d*)\s*(K?)', clean_d)
            if match:
                val = float(match.group(1))
                if match.group(2) == 'K':
                    val *= 1000
                return val
            nums = re.findall(r'\d+', clean_d)
            if nums:
                return float(nums[0])
    for detail in details_list:
        d_up = detail.upper()
        if 'FOR' in d_up and ('PCS' in d_up or 'PC' in d_up):
            match = re.search(r'FOR\s+(\d+\.?\d*)\s*(K?)\s*PCS?', d_up)
            if match:
                val = float(match.group(1))
                if match.group(2) == 'K':
                    val *= 1000
                return val
    return None


def extract_sourcer(details_list):
    for detail in details_list:
        if 'SOURCER' not in detail.upper():
            continue
        match = re.search(
            r'SOURCER\s*:?\s*([A-Za-z\u0590-\u05FF]{2,})',
            detail,
            re.IGNORECASE,
        )
        if match:
            name = match.group(1).strip()
            if name.upper() not in ('NAME', 'BY', 'IS', 'THE'):
                return name.capitalize()
    return None


def extract_date(details_list):
    for detail in details_list:
        if 'DATE' not in detail.upper():
            continue
        m = re.search(
            r'(\d{1,2})(?:st|nd|rd|th)?\s*[,\s]+([A-Za-z]{3,9})\s*[,\s]+(\d{4})',
            detail, re.IGNORECASE
        )
        if m:
            return f"{m.group(1)} {m.group(2).capitalize()} {m.group(3)}"
        m = re.search(
            r'([A-Za-z]{3,9})\s+(\d{1,2})[,\s]+(\d{4})',
            detail, re.IGNORECASE
        )
        if m:
            return f"{m.group(2)} {m.group(1).capitalize()} {m.group(3)}"
        m = re.search(
            r'(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
            detail
        )
        if m:
            return m.group(1).strip()
    return None


def extract_categories(details_list):
    found_categories = set()
    text_to_scan = ""
    for line in details_list:
        if not any(pk in line.upper() for pk in PACKING_KEYWORDS):
            text_to_scan += " " + line.lower()
    for cat, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_to_scan):
                found_categories.add(cat)
    if re.search(r'\b(bottle|flask|tumbler|drinkware|thermos|cooler)\b', text_to_scan):
        found_categories.update(['בקבוקים, כוסות ושתייה', 'עונות (קיץ/חורף)', 'מחנאות, נופש וספורט'])
    if re.search(
        r'\b(soccer|football|כדורגל|basketball|tennis|כדורסל|טניס|volleyball|'
        r'כדורעף|ping pong|table tennis|פינג פונג)\b',
        text_to_scan,
    ):
        found_categories.add('מחנאות, נופש וספורט')
    return list(found_categories)


def extract_min_price(details_list):
    prices = []
    for detail in details_list:
        d_up = detail.upper()
        if 'USD' in d_up or 'PRICE' in d_up or '$' in d_up:
            for match in re.findall(r'\d*\.\d+|\d+', detail):
                try:
                    val = float(match)
                    if 0 < val < 10000:
                        prices.append(val)
                except:
                    pass
    return min(prices) if prices else None


def extract_price_display(details_list):
    for detail in details_list:
        d_up = detail.upper()
        if 'USD' in d_up or 'PRICE' in d_up or '$' in d_up:
            return detail.strip()
    return None


def extract_delivery_days(details_list):
    for detail in details_list:
        d_up = detail.upper()
        if ('DELIVERY' in d_up or 'DAYS' in d_up or 'LEAD TIME' in d_up) and 'SAMPLE' not in d_up:
            nums = re.findall(r'\d+', detail)
            if nums:
                return max(int(n) for n in nums)
    return None


def extract_capacity(full_text):
    matches = re.findall(r'(\d{2,4})\s*(ml|oz)', full_text.lower())
    return f"{matches[0][0]}{matches[0][1]}" if matches else None


def extract_materials(full_text):
    """
    חיפוש מדויק בשורת Material: בלבד.
    מחזיר רק שמות חומרים אמיתיים — לא מידות, כמויות, תאריכים.
    """
    import re as _re
    materials = []

    # חיפוש שורת Material: בלבד (חייבת נקודתיים)
    mat_match = _re.search(
        r'(?:^|\n)\s*(?:material|חומר)\s*:\s*(.+?)(?:\n|$)',
        full_text,
        _re.IGNORECASE | _re.MULTILINE,
    )
    if not mat_match:
        return []

    raw_val = mat_match.group(1).strip()

    # סינון: אם הערך מכיל מספרים עם יחידות (מידה/כמות) — לא חומר
    if _re.search(r'\d+\s*(?:mm|cm|pcs|pc|kgs?|g\.?w|n\.?w|\*)', raw_val, _re.IGNORECASE):
        return []

    # פיצול לפי פסיק / slash
    for part in _re.split(r'[,/]', raw_val):
        part = part.strip()
        if not part or len(part) > 50:
            continue

        # סינון נוסף: מילים שאינן חומר
        skip_words = ['usd', 'price', 'exw', 'fob', 'days', 'pcs',
                      'deposit', 'balance', 'payment', 'sample', 'order']
        if any(w in part.lower() for w in skip_words):
            continue

        part_lower = part.lower()

        # מיפוי לשמות סטנדרטיים
        if 'stainless' in part_lower or '304' in part_lower or '316' in part_lower:
            materials.append('Stainless Steel')
        elif 'plastic' in part_lower or _re.search(r'\bpp\b', part_lower) or 'tritan' in part_lower:
            materials.append('Plastic')
        elif 'bamboo'   in part_lower: materials.append('Bamboo')
        elif 'glass'    in part_lower: materials.append('Glass')
        elif 'silicone' in part_lower: materials.append('Silicone')
        elif 'ceramic'  in part_lower: materials.append('Ceramic')
        elif 'tin'      in part_lower or 'tinplate' in part_lower: materials.append('Tin')
        elif 'aluminum' in part_lower or 'aluminium' in part_lower: materials.append('Aluminum')
        elif 'wood'     in part_lower or 'wooden'   in part_lower: materials.append('Wood')
        elif 'leather'  in part_lower: materials.append('Leather')
        elif 'cotton'   in part_lower: materials.append('Cotton')
        elif 'rpet'     in part_lower or 'recycled' in part_lower: materials.append('Recycled')
        elif 'cork'     in part_lower: materials.append('Cork')
        elif 'wheat'    in part_lower: materials.append('Wheat Straw')
        elif 'pvc'      in part_lower: materials.append('PVC')
        elif 'nylon'    in part_lower: materials.append('Nylon')
        elif 'rubber'   in part_lower: materials.append('Rubber')
        elif len(part) >= 2:
            # חומר לא מוכר — שומר כ-Title Case
            materials.append(part.title())

    return list(dict.fromkeys(materials))

def _extract_date_value(raw):
    """חותך את הערך אחרי DATE: ומנקה רווחים."""
    if ':' in raw:
        after = raw.split(':', 1)[1]
    else:
        after = re.split(r'DATE', raw, maxsplit=1, flags=re.IGNORECASE)[-1]
    value = after.strip().strip('.')
    return value if value else None


def normalize_text(text):
    """Lowercase, keep alphanumeric + Hebrew + spaces."""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r'[^a-zA-Z0-9֐-׿ ]', ' ', text).lower()


def transform_he_to_en(text):
    he_en_map = {
        'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g',
        'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n',
        'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u',
        'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y',
    }
    return "".join(he_en_map.get(char, char) for char in text.lower())


def classify_details(display_list):
    """Split display_list into labeled buckets for rendering."""
    general_info, price_info, packing_info = [], [], []
    delivery_info, sample_info, other_info  = [], [], []
    for detail in display_list:
        if contains_chinese(detail):
            continue
        d_up = detail.upper()
        if 'MOQ' in d_up:
            continue
        if any(k in d_up for k in PRICE_KEYWORDS) or '$' in detail:
            price_info.append(detail)
        elif any(k in d_up for k in PACKING_KEYS):
            packing_info.append(detail)
        elif 'SAMPLE' in d_up and any(k in d_up for k in ['TIME', 'DAY', 'LEAD']):
            sample_info.append(detail)
        elif any(k in d_up for k in DELIVERY_KEYS):
            delivery_info.append(detail)
        elif any(k in d_up for k in GENERAL_KEYS):
            general_info.append(detail)
        else:
            other_info.append(detail)
    return general_info, price_info, packing_info, delivery_info, sample_info, other_info

def extract_file_header(df_file):
    sourcer = None
    date    = None
    max_rows = min(20, len(df_file))
    max_cols = min(10, len(df_file.columns))
    for r in range(max_rows):
        for c in range(max_cols):
            cell = df_file.iloc[r, c]
            if pd.isna(cell):
                continue
            cell_str = str(cell).strip()
            if sourcer is None and re.search(r'SOURCER', cell_str, re.IGNORECASE):
                m = re.search(
                    r'SOURCER\s*:?\s*([A-Za-z\u0590-\u05FF]{2,})',
                    cell_str, re.IGNORECASE
                )
                if m:
                    name = m.group(1).strip()
                    if name.upper() not in ('NAME', 'BY', 'IS', 'THE'):
                        sourcer = name.capitalize()
                else:
                    for dc in range(1, 3):
                        if c + dc < max_cols:
                            nc = df_file.iloc[r, c + dc]
                            if not pd.isna(nc):
                                name = str(nc).strip()
                                if re.match(r'^[A-Za-z\u0590-\u05FF]{2,}$', name):
                                    if name.upper() not in ('NAME', 'BY', 'IS', 'THE'):
                                        sourcer = name.capitalize()
                                        break
            if date is None and re.search(r'\bDATE\b', cell_str, re.IGNORECASE):
                val = _extract_date_value(cell_str)
                if val:
                    date = val
                else:
                    for dc in range(1, 3):
                        if c + dc < max_cols:
                            nc = df_file.iloc[r, c + dc]
                            if not pd.isna(nc):
                                candidate = str(nc).strip().strip('.')
                                if candidate:
                                    date = candidate
                                    break
            if sourcer and date:
                return sourcer, date
    return sourcer, date


def get_gdrive_service():
    try:
        encoded_key = constants.GCP_SERVICE_ACCOUNT
        decoded_key = base64.b64decode(encoded_key).decode('utf-8')
        info  = json.loads(decoded_key)
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"שגיאת חיבור: {e}")
        return None


@st.cache_data(ttl=3600)
def get_image_base64(file_id):
    service = get_gdrive_service()
    if not service:
        return None
    try:
        from googleapiclient.http import MediaIoBaseDownload
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except:
        return None


@st.cache_data(ttl=600)
def load_all_data():
    service = get_gdrive_service()
    if not service:
        return pd.DataFrame(), {}

    results = service.files().list(
        q=f"'{FOLDER_ID_EXCELS}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    all_products = []

    files_found = results.get('files', [])
    st.write(f"🔎 DEBUG2: נמצאו {len(files_found)} קבצי אקסל בדרייב")

    for item in files_found:
        try:
            request = service.files().get_media(fileId=item['id'], supportsAllDrives=True)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            df_file = pd.read_excel(
                fh, header=None,
                engine='xlrd' if item['name'].endswith('.xls') else None,
            )
            file_sourcer, file_date = extract_file_header(df_file)
            skip_until = -1
            for idx in range(len(df_file)):
                if idx < skip_until:
                    continue
                row_str = " ".join(df_file.iloc[idx].dropna().astype(str))
                if any(k in row_str.upper() for k in ITEM_TRIGGER_KEYS):
                    details  = []
                    item_key = ""
                    for offset in range(25):
                        curr_idx = idx + offset
                        if curr_idx >= len(df_file):
                            skip_until = curr_idx
                            break
                        b_row = df_file.iloc[curr_idx].dropna().astype(str)
                        line  = re.sub(r'\s+', ' ', " ".join(b_row)).strip()
                        if offset > 1 and any(
                            k in line.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', '*ITEM']
                        ):
                            skip_until = curr_idx
                            break
                        if line and not any(x in line.upper() for x in SKIP_CONTENT_KEYS):
                            details.append(line)
                            if 'ITEM' in line.upper() and not item_key:
                                item_key = line
                    else:
                        skip_until = idx + 25
                    if details:
                        full_text_str = " ".join(details)
                        min_p = extract_min_price(details)
                        all_products.append({
                            'item_key':        item_key if item_key else details[0],
                            'display_list':    details,
                            'full_text':       full_text_str,
                            'normalized_text': normalize_text(full_text_str),
                            'file_source':     item['name'],
                            'base_filename':   item['name'].rsplit('.', 1)[0],
                            'row_index':       idx,
                            'min_price':       min_p,
                            'price_display':   extract_price_display(details),
                            'moq':             extract_moq(details),
                            'delivery_days':   extract_delivery_days(details),
                            'capacity':        extract_capacity(full_text_str),
                            'materials':       extract_materials(full_text_str),
                            'categories':      extract_categories(details),
                            'sourcer':         file_sourcer,
                            'date':            file_date,
                        })
        except Exception as _e:
            st.warning(f"שגיאה בקובץ {item.get('name','?')}: {_e}")
            continue

    img_results = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map


# =============================================================================
# UI COMPONENTS
# =============================================================================

def _resolve_image_ids(row, img_map):
    """
    מחזיר רשימה מסודרת של כל ה-image IDs השייכים למוצר זה.
    המחלץ שומר: base_row_<first_top_row>_img_<N>.png
    app.py מחפש לפי row_index שהוא מספר השורה של ITEM/DESCRIPTION.
    כיוון שהתמונה תמיד מתחילה כמה שורות לפני הטקסט,
    מחפשים את התמונה הכי קרובה ל-row_index (בטווח סביר).
    """
    base_name_clean = normalize_text(row['base_filename'])
    row_index       = row['row_index']

    # כל התמונות של הקובץ הזה
    file_imgs = {
        name: img_id for name, img_id in img_map.items()
        if base_name_clean in normalize_text(name)
    }
    if not file_imgs:
        return []

    # חיפוש פורמט חדש: base_row_<R>_img_<N>.png
    # מחפש את ה-R הכי קרוב ל-row_index (תמונה לפני או ב-row_index)
    row_nums = set()
    for name in file_imgs:
        m = re.search(r'_row_(\d+)_img_', normalize_text(name))
        if m:
            row_nums.add(int(m.group(1)))

    if row_nums:
        # ה-R הכי קרוב שהוא <= row_index + 5
        candidates = [r for r in row_nums if r <= row_index + 5]
        if candidates:
            best_row = max(candidates)  # הכי קרוב מלמטה
            matched = {
                name: img_id for name, img_id in file_imgs.items()
                if f"_row_{best_row}_img_" in normalize_text(name)
            }
            def img_sort_key(name):
                m2 = re.search(r'_img_(\d+)', name, re.IGNORECASE)
                return int(m2.group(1)) if m2 else 0
            return [img_id for name, img_id in sorted(matched.items(), key=lambda x: img_sort_key(x[0]))]

    return []


def _build_gallery_html(img_ids, card_uid):
    """
    גלריה עם חצים + נקודות + zoom בהover.
    תומך במובייל (swipe) ובדסקטופ (חצים + hover zoom).
    """
    if not img_ids:
        return '<div class="img-box"><span style="color:#ccc;font-size:11px;">📷 לא נמצאה תמונה</span></div>'

    # טוען את כל התמונות
    images_b64 = []
    for img_id in img_ids:
        b64 = get_image_base64(img_id)
        if b64:
            images_b64.append(b64)

    if not images_b64:
        return '<div class="img-box"><span style="color:#ccc;font-size:11px;">📷 לא נמצאה תמונה</span></div>'

    total = len(images_b64)
    uid   = card_uid.replace('-', '_').replace('.', '_')

    # בניית תגי img
    slides_html = ""
    for idx, b64 in enumerate(images_b64):
        display = "block" if idx == 0 else "none"
        slides_html += (
            f'<img id="gimg_{uid}_{idx}" '
            f'src="data:image/jpeg;base64,{b64}" '
            f'alt="product image" '
            f'style="max-width:100%;max-height:220px;object-fit:contain;'
            f'border-radius:4px;cursor:zoom-in;display:{display};" '
            f'class="gallery-img" data-uid="{uid}">'
        )

    # חצים — מוצגים רק אם יש יותר מתמונה אחת
    arrows_html = ""
    if total > 1:
        arrows_html = f"""
        <div onclick="galleryPrev('{uid}')"
             style="position:absolute;left:4px;top:50%;transform:translateY(-50%);
                    z-index:10;background:rgba(0,0,0,0.45);color:#fff;
                    border-radius:50%;width:28px;height:28px;display:flex;
                    align-items:center;justify-content:center;
                    cursor:pointer;font-size:16px;user-select:none;">&#8249;</div>
        <div onclick="galleryNext('{uid}')"
             style="position:absolute;right:4px;top:50%;transform:translateY(-50%);
                    z-index:10;background:rgba(0,0,0,0.45);color:#fff;
                    border-radius:50%;width:28px;height:28px;display:flex;
                    align-items:center;justify-content:center;
                    cursor:pointer;font-size:16px;user-select:none;">&#8250;</div>
        """

    # נקודות — מוצגות רק אם יש יותר מתמונה אחת
    dots_html = ""
    if total > 1:
        dots_inner = ""
        for idx in range(total):
            active_style = "background:#555;" if idx == 0 else "background:#ccc;"
            dots_inner += (
                f'<span id="gdot_{uid}_{idx}" '
                f'onclick="galleryGoto(\'{uid}\',{idx})" '
                f'style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                f'margin:0 3px;cursor:pointer;transition:background 0.2s;{active_style}"></span>'
            )
        dots_html = (
            f'<div style="text-align:center;padding:4px 0;flex-shrink:0;">'
            f'{dots_inner}</div>'
        )

    # counter
    counter_html = ""
    if total > 1:
        counter_html = (
            f'<div id="gcnt_{uid}" '
            f'style="position:absolute;bottom:6px;right:8px;'
            f'background:rgba(0,0,0,0.5);color:#fff;font-size:10px;'
            f'padding:1px 6px;border-radius:10px;z-index:10;">'
            f'1/{total}</div>'
        )

    js = f"""
<script>
(function(){{
  var total_{uid} = {total};
  var cur_{uid}   = 0;

  window.galleryNext = window.galleryNext || function(uid) {{
    var fn = window['_galleryNext_' + uid];
    if (fn) fn();
  }};
  window.galleryPrev = window.galleryPrev || function(uid) {{
    var fn = window['_galleryPrev_' + uid];
    if (fn) fn();
  }};
  window.galleryGoto = window.galleryGoto || function(uid, idx) {{
    var fn = window['_galleryGoto_' + uid];
    if (fn) fn(idx);
  }};

  function show_{uid}(idx) {{
    var doc = window.parent ? window.parent.document : document;
    for (var i = 0; i < total_{uid}; i++) {{
      var el = doc.getElementById('gimg_{uid}_' + i);
      var dt = doc.getElementById('gdot_{uid}_' + i);
      if (el) el.style.display = (i === idx) ? 'block' : 'none';
      if (dt) dt.style.background = (i === idx) ? '#555' : '#ccc';
    }}
    var cnt = doc.getElementById('gcnt_{uid}');
    if (cnt) cnt.textContent = (idx+1) + '/' + total_{uid};
    cur_{uid} = idx;
  }}

  window['_galleryNext_' + '{uid}'] = function() {{
    show_{uid}((cur_{uid} + 1) % total_{uid});
  }};
  window['_galleryPrev_' + '{uid}'] = function() {{
    show_{uid}((cur_{uid} - 1 + total_{uid}) % total_{uid});
  }};
  window['_galleryGoto_' + '{uid}'] = function(idx) {{
    show_{uid}(idx);
  }};

  // Swipe support
  var box = (window.parent ? window.parent.document : document).getElementById('gbox_{uid}');
  if (box) {{
    var startX = 0;
    box.addEventListener('touchstart', function(e) {{ startX = e.touches[0].clientX; }}, {{passive:true}});
    box.addEventListener('touchend', function(e) {{
      var diff = startX - e.changedTouches[0].clientX;
      if (Math.abs(diff) > 40) {{
        if (diff > 0) window['_galleryNext_{uid}']();
        else          window['_galleryPrev_{uid}']();
      }}
    }}, {{passive:true}});
  }}
}})();
</script>
"""

    return f"""
<div style="display:flex;flex-direction:column;flex-shrink:0;">
  <div id="gbox_{uid}"
       style="width:100%;height:220px;min-height:220px;max-height:220px;
              overflow:hidden;border-radius:8px;background:#fafafa;
              display:flex;align-items:center;justify-content:center;
              position:relative;margin-bottom:4px;">
    {slides_html}
    {arrows_html}
    {counter_html}
  </div>
  {dots_html}
</div>
{js}
"""


def _build_meta_header_html(row):
    date_str    = row.get('date') or 'No Date'
    sourcer_str = row.get('sourcer')
    if sourcer_str:
        content = f"📅 {date_str} &nbsp;|&nbsp; 👤 {sourcer_str}"
    else:
        content = f"📅 {date_str}"
    return (
        f"<div style='font-size:10px; color:#888; font-family:Arial,sans-serif; "
        f"margin-bottom:6px; margin-top:0; white-space:nowrap; flex-shrink:0; "
        f"overflow:hidden; text-overflow:ellipsis; direction:ltr; text-align:left;'>"
        f"{content}</div>"
    )


def _build_product_title_html(row):
    """
    כותרת המוצר — DESCRIPTION בעדיפות, אחר כך ITEM NO / ITEM REF.
    חיפוש מדויק: השורה חייבת להתחיל ב-DESCRIPTION: או ITEM NO:
    """
    import re as _re
    title = ""

    for detail in row.get('display_list', []):
        # מחפש בדיוק: DESCRIPTION: <ערך>
        m = _re.match(r'^\s*DESCRIPTION\s*:\s*(.+)', detail, _re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            break

    if not title:
        for detail in row.get('display_list', []):
            # מחפש: ITEM NO: או ITEM REF: או ITEM:
            m = _re.match(r'^\s*(?:ITEM\s*(?:NO|REF|NUMBER)?)\s*:\s*(.+)', detail, _re.IGNORECASE)
            if m:
                title = m.group(1).strip()
                break

    if not title:
        return ""

    if len(title) > 60:
        title = title[:57] + "..."

    return (
        f"<div style='font-size:13px; font-weight:900; color:#111; "
        f"margin-bottom:5px; flex-shrink:0; overflow:hidden; "
        f"text-overflow:ellipsis; white-space:nowrap; direction:ltr;'>"
        f"{title}</div>"
    )


def _build_tags_html(row):
    moq_val = format_moq_display(row['moq'])
    moq_bg  = COLOR_MOQ_NAN if moq_val == "NAN" else COLOR_MOQ_OK
    moq_fg  = "#fff"         if moq_val == "NAN" else "#000"
    moq_tag = (
        f"<span style='background:{moq_bg}; color:{moq_fg}; padding:3px 8px; "
        f"border-radius:4px; font-size:11px; font-weight:bold; white-space:nowrap;'>"
        f"📦 MOQ: {moq_val}</span>"
    )
    capacity_tag = ""
    if row.get('capacity'):
        capacity_tag = (
            f"<span style='background:{COLOR_CAPACITY_BG}; color:{COLOR_CAPACITY_TEXT}; "
            f"padding:3px 8px; border-radius:4px; font-size:11px; white-space:nowrap;'>"
            f"💧 {row['capacity']}</span>"
        )
    category_tags = "".join(
        f"<span style='background:{COLOR_TAG_BG}; color:#fff; padding:3px 8px; "
        f"border-radius:4px; font-size:11px; white-space:nowrap;'>🏷️ {cat}</span>"
        for cat in (row.get('categories') or [])
    )
    return (
        f"<div style='display:flex; flex-wrap:wrap; gap:4px; "
        f"margin-bottom:6px; direction:ltr;'>"
        f"{moq_tag}{capacity_tag}{category_tags}</div>"
    )


def _build_price_footer_html(row, usd_ils_rate):
    min_price     = row.get('min_price')
    price_display = row.get('price_display')
    price_html = ""
    if price_display:
        ils_part = ""
        if min_price and usd_ils_rate and usd_ils_rate > 0:
            ils_val  = min_price * usd_ils_rate
            ils_part = (
                f"&nbsp;<span style='color:{COLOR_PRICE_ILS}; font-weight:800; font-size:14px;'>"
                f"| ₪&nbsp;{ils_val:.2f}</span>"
            )
        price_html = (
            f"<div style='color:{COLOR_PRICE}; font-weight:900; font-size:14px; "
            f"margin-bottom:3px; line-height:1.5; "
            f"white-space:normal; overflow:visible; word-break:break-word;'>"
            f"💰 {price_display} {ils_part}"
            f"</div>"
        )
    meta_html = (
        f"<div style='font-size:10px; color:{COLOR_SOURCE}; margin-top:3px; "
        f"white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>"
        f"📂 {row['file_source']}</div>"
    )
    return f'<div class="card-footer">{price_html}{meta_html}</div>'


def render_product_card(row, i, img_map, usd_ils_rate):
    unique_item_id = f"{row['base_filename']}_{row['row_index']}"
    uid_clean      = unique_item_id.replace(' ', '_').replace('.', '_')

    with st.container(border=True):
        is_selected = unique_item_id in st.session_state.selected_items
        if st.checkbox("➕ בחר לשליחה", value=is_selected, key=f"chk_{unique_item_id}"):
            if not is_selected:
                st.session_state.selected_items[unique_item_id] = row.to_dict()
                st.rerun()
        else:
            if is_selected:
                del st.session_state.selected_items[unique_item_id]
                st.rerun()

        meta_header = _build_meta_header_html(row)
        title_html  = _build_product_title_html(row)

        # גלריה — כל התמונות של המוצר
        img_ids   = _resolve_image_ids(row, img_map)
        gallery   = _build_gallery_html(img_ids, uid_clean)
        tags_html = _build_tags_html(row)

        general_info, price_info, packing_info, delivery_info, sample_info, other_info = \
            classify_details(row['display_list'])

        details_inner = ""
        for info in general_info:
            details_inner += (
                f"<div style='font-weight:800; font-size:13px; color:{COLOR_GENERAL}; "
                f"margin-bottom:4px;'>{info}</div>"
            )
        for info in sample_info:
            details_inner += (
                f"<div style='font-size:12px; color:{COLOR_SAMPLE}; "
                f"font-weight:700; margin-bottom:3px;'>⏱️ {info}</div>"
            )
        for info in delivery_info:
            details_inner += (
                f"<div style='font-size:12px; color:{COLOR_DELIVERY}; "
                f"font-weight:600; margin-bottom:2px;'>🚚 {info}</div>"
            )
        for info in packing_info:
            details_inner += (
                f"<div style='font-size:12px; color:{COLOR_PACKING}; "
                f"margin-bottom:2px;'>📦 {info}</div>"
            )
        for info in other_info:
            details_inner += (
                f"<div style='font-size:11px; color:{COLOR_OTHER};'>• {info}</div>"
            )

        details_html = f'<div class="card-details">{details_inner}</div>'
        footer_html  = _build_price_footer_html(row, usd_ils_rate)

        card_html = (
            f'<div style="display:flex; flex-direction:column; '
            f'height:640px; max-height:640px; overflow:hidden; '
            f'direction:ltr; text-align:left;">'
            f'{meta_header}'
            f'{title_html}'
            f'{gallery}'
            f'<div style="flex-shrink:0;">{tags_html}</div>'
            f'{details_html}{footer_html}'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        st.markdown(card_html, unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

def _render_cart_section():
    st.markdown(
        f"<div style='font-family:Arial,sans-serif !important;'>"
        f"<h2 style='font-family:Arial,sans-serif !important; color:{COLOR_PRIMARY}; "
        f"font-weight:900; font-size:1.6rem; "
        f"border-bottom:3px solid {COLOR_SIDEBAR_BORDER}; "
        f"padding-bottom:6px; margin-bottom:18px; margin-top:0; "
        f"text-align:right; direction:rtl;'>"
        f"<span style='font-family:Arial,sans-serif !important;'>🛒 מוצרים לשליחה</span>"
        f"</h2></div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.selected_items:
        st.info("לא נבחרו מוצרים עדיין.")
        return

    st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")

    email_body = "שלום,\n\nלהלן פרטי המוצרים לבקשתך:\n\n"
    for item_data in st.session_state.selected_items.values():
        email_body += f"--- {item_data['item_key']} ---\n"
        for detail in item_data['display_list']:
            if (
                "Unnamed" not in detail
                and not contains_chinese(detail)
                and "MOQ" not in detail.upper()
            ):
                email_body += f"• {detail}\n"
        email_body += f"מקור: {item_data['file_source']}\n\n"
    email_body += "בברכה,\nNext Design"

    encoded_subject = urllib.parse.quote("Next Design - פרטי מוצרים")
    encoded_body    = urllib.parse.quote(email_body)
    st.markdown(
        f'<a href="mailto:?subject={encoded_subject}&body={encoded_body}" '
        f'class="email-btn" target="_blank">✉️ שלח במייל עכשיו</a>',
        unsafe_allow_html=True,
    )
    if st.button("🗑️ נקה רשימה", use_container_width=True):
        st.session_state.selected_items = {}


def render_sidebar(df):
    with st.sidebar:

        # 1. עגלה
        _render_cart_section()
        st.divider()

        # 2. סינון
        st.markdown(
            f"<div style='font-family:Arial,sans-serif !important;'>"
            f"<h2 style='font-family:Arial,sans-serif !important; color:{COLOR_PRIMARY}; "
            f"font-weight:900; font-size:1.6rem; "
            f"border-bottom:3px solid {COLOR_SIDEBAR_BORDER}; "
            f"padding-bottom:6px; margin-bottom:18px; margin-top:0; "
            f"text-align:right; direction:rtl;'>"
            f"<span style='font-family:Arial,sans-serif !important;'>⚙️ סינון חכם</span>"
            f"</h2></div>",
            unsafe_allow_html=True,
        )

        selected_categories = st.multiselect(
            "קטגוריה (Category)", list(CATEGORY_MAP.keys()), placeholder="בחר קטגוריות..."
        )

        # ── טווח מחיר: שני שדות הזנה במקום סקאלה ──────────────────
        st.markdown(
            "<p style='font-family:Arial,sans-serif; color:#334155; font-weight:700; "
            "font-size:15px; text-align:right; direction:rtl; margin-bottom:4px;'>"
            "טווח מחיר ליח' (USD)</p>",
            unsafe_allow_html=True,
        )
        col_min, col_max = st.columns(2)
        with col_min:
            price_min = st.number_input(
                "מינימום", min_value=0.0, value=0.0,
                step=0.1, format="%.2f",
            )
        with col_max:
            price_max = st.number_input(
                "מקסימום", min_value=0.0, value=200.0,
                step=0.1, format="%.2f",
            )
        # ────────────────────────────────────────────────────────────

        usd_ils_rate = st.number_input(
            "שער דולר (USD/ILS ₪)",
            min_value=0.0, value=DEFAULT_USD_ILS, step=0.01, format="%.2f",
            help="המחיר בשקלים יחושב לפי שער זה — מוצג בסגול בכרטיסייה",
        )
        max_moq = st.number_input(
            "MOQ מקסימלי (כמות מינימלית)", min_value=0, value=None,
            placeholder="ללא הגבלה...", step=500,
        )
        max_delivery = st.slider(
            "זמן אספקה מקסימלי (ימים)", min_value=5, max_value=90, value=90, step=5
        )

        available_capacities = (
            sorted([c for c in df['capacity'].unique() if c]) if not df.empty else []
        )
        # רשימת חומרים דינמית — נשאבת מהנתונים + חומרי בסיס קבועים
        BASE_MATERIALS = [
            "Stainless Steel", "Plastic", "Bamboo", "Glass",
            "Silicone", "Ceramic", "Tin", "Aluminum", "Wood",
            "Leather", "Cotton", "Recycled", "Cork", "Wheat Straw",
        ]
        if not df.empty:
            from_data = [
                m for mlist in df['materials'].dropna()
                for m in (mlist if isinstance(mlist, list) else [])
                if m
            ]
            available_materials = sorted(set(BASE_MATERIALS + from_data))
        else:
            available_materials = BASE_MATERIALS
        selected_materials = st.multiselect(
            "חומר (Material)",
            available_materials,
            placeholder="בחר חומרים...",
        )
        selected_capacities = st.multiselect(
            "נפח (Capacity)", available_capacities, placeholder="בחר נפחים (למשל 500ml)..."
        )

        available_sourcers = (
            sorted([s for s in df['sourcer'].dropna().unique().tolist() if s])
            if not df.empty else []
        )
        selected_sourcers = st.multiselect(
            "איש רכש (Sourcer)", available_sourcers, placeholder="בחר איש רכש..."
        )

        st.divider()

        # 3. רענון
        if st.button("🔄 רענון נתונים", use_container_width=True):
            st.cache_data.clear()
            st.success("הנתונים רועננו בהצלחה!")
            st.rerun()

        st.markdown("<div style='height:80px;'></div>", unsafe_allow_html=True)

    return dict(
        selected_categories=selected_categories,
        price_min=price_min,
        price_max=price_max,
        usd_ils_rate=usd_ils_rate,
        max_moq=max_moq,
        max_delivery=max_delivery,
        selected_materials=selected_materials,
        selected_capacities=selected_capacities,
        selected_sourcers=selected_sourcers,
    )


# =============================================================================
# PAGE HEADER
# =============================================================================

def render_page_header():
    st.markdown("""
        <div style="text-align:center; margin-bottom:40px; margin-top:10px; direction:rtl;">
            <a href="https://nextd.wallak.co.il/" target="_blank" style="text-decoration:none;">
                <h1 style="font-family:'Arial',sans-serif; font-weight:900; letter-spacing:1px;
                           color:#000; font-size:46px; margin-bottom:0;">
                    <span style="background-color:#000; color:#fff; padding:0 12px;
                                 border-radius:6px; margin-right:5px;">NEXT</span>DESIGN
                </h1>
            </a>
            <h3 style="font-family:'Arial',sans-serif; color:#666; font-weight:500; margin-top:5px;">
                קטלוג הצעות מחיר ביבוא 🔎
            </h3>
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# PAGINATION
# =============================================================================

def render_pagination(total_products):
    st.markdown("<br>", unsafe_allow_html=True)
    total_pages = (total_products + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.session_state.current_page > 0:
            if st.button("⬅️ קודם", use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()

    with col_info:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>"
            f"עמוד {st.session_state.current_page + 1} מתוך {total_pages}</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        if (st.session_state.current_page + 1) * PRODUCTS_PER_PAGE < total_products:
            if st.button("הבא ➡️", use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()


# =============================================================================
# FILTERING
# =============================================================================

def apply_filters(df, search_input, filters):
    results = df.copy()

    query = search_input.strip()
    if query and query.upper() != "ALL":
        for word in query.split():
            norm_word  = normalize_text(word)
            trans_word = normalize_text(transform_he_to_en(word))
            results = results[
                results['normalized_text'].str.contains(norm_word,  na=False) |
                results['normalized_text'].str.contains(trans_word, na=False)
            ]

    if filters['selected_categories']:
        results = results[results['categories'].apply(
            lambda cats: any(c in cats for c in filters['selected_categories'])
        )]

    if filters['price_min'] > 0.0 or filters['price_max'] < 200.0:
        results = results[results['min_price'].apply(
            lambda x: x is not None and filters['price_min'] <= x <= filters['price_max']
        )]

    if filters['max_moq'] is not None:
        results = results[results['moq'].apply(lambda x: x is None or x <= filters['max_moq'])]

    if filters['max_delivery'] < 90:
        results = results[results['delivery_days'].apply(
            lambda x: x is not None and x <= filters['max_delivery']
        )]

    if filters['selected_materials']:
        results = results[results['materials'].apply(
            lambda x: any(m in x for m in filters['selected_materials'])
        )]

    if filters['selected_capacities']:
        results = results[results['capacity'].isin(filters['selected_capacities'])]

    if filters['selected_sourcers']:
        results = results[results['sourcer'].isin(filters['selected_sourcers'])]

    return results.drop_duplicates(subset=['item_key', 'file_source'])


# =============================================================================
# MAIN
# =============================================================================

def main():
    render_page_header()

    # נקה cache בעת אתחול ראשון של session
    if 'cache_cleared' not in st.session_state:
        st.cache_data.clear()
        st.session_state.cache_cleared = True

    if 'df' not in st.session_state or 'img_map' not in st.session_state:
        st.session_state.df, st.session_state.img_map = load_all_data()

    df      = st.session_state.df
    img_map = st.session_state.img_map

    filters = render_sidebar(df)

    search_input = st.text_input(
        "", placeholder="🔍 הקלד שם מוצר לחיפוש (או ALL להצגת כל הקטלוג)..."
    )

    # DEBUG — יוסר אחרי אבחון
    st.write(f"🔎 DEBUG: df rows={len(df)}, search='{search_input}', "
             f"cats={filters['selected_categories']}, mats={filters['selected_materials']}")

    should_show = (
        bool(search_input.strip())
        or bool(filters['selected_categories'])
        or bool(filters['selected_materials'])
        or bool(filters['selected_capacities'])
        or bool(filters['selected_sourcers'])
    )
    if df.empty or not should_show:
        return

    results = apply_filters(df, search_input, filters)

    if results.empty:
        st.warning("לא נמצאו תוצאות התואמות לחיפוש ולסינונים שלך.")
        return

    current_filters = (
        search_input,
        tuple(filters['selected_categories']),
        filters['price_min'], filters['price_max'],
        filters['max_moq'], filters['max_delivery'],
        tuple(filters['selected_materials']),
        tuple(filters['selected_capacities']),
        tuple(filters['selected_sourcers']),
    )
    if st.session_state.last_filters != current_filters:
        st.session_state.current_page = 0
        st.session_state.last_filters = current_filters

    total_products = len(results)
    start          = st.session_state.current_page * PRODUCTS_PER_PAGE
    end            = min(start + PRODUCTS_PER_PAGE, total_products)
    page_results   = results.iloc[start:end]

    st.write("<br>", unsafe_allow_html=True)
    cols = st.columns(COLUMNS_PER_ROW)
    for i, (_, row) in enumerate(page_results.iterrows()):
        with cols[i % COLUMNS_PER_ROW]:
            render_product_card(row, i, img_map, filters['usd_ils_rate'])

    render_pagination(total_products)


if __name__ == "__main__" or True:
    main()
