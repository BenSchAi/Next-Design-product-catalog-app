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
# CONSTANTS - Design tokens & configuration (שינוי עיצוב מקום אחד בלבד)
# =============================================================================

# --- Google Drive Folder IDs ---
FOLDER_ID_EXCELS = "1x7bE0YmGhrK_-0f06ixwlOKqquV_8AHZ"
FOLDER_ID_IMAGES = "1R4nm5cf2NEWB30IceF4cL5oShNlqurPS"

# --- Pagination ---
PRODUCTS_PER_PAGE = 12
COLUMNS_PER_ROW   = 4

# --- Color palette ---
COLOR_PRIMARY        = "#1E3A8A"   # כחול נייבי (כותרות סיידבר)
COLOR_SIDEBAR_BORDER = "#BFDBFE"   # תכלת בהיר (קו תחתון כותרות)
COLOR_TEXT_DARK      = "#334155"   # אפור-פחם (תוויות סינון)
COLOR_PRICE          = "#27ae60"   # ירוק (מחיר USD)
COLOR_PRICE_ILS      = "#7C3AED"   # סגול עמוק (מחיר ILS) — בולט ושונה מהדולר
COLOR_DELIVERY       = "#444"      # אפור כהה (משלוח)
COLOR_PACKING        = "#666"      # אפור בינוני (אריזה)
COLOR_OTHER          = "#888"      # אפור בהיר (שאר)
COLOR_GENERAL        = "#222"      # כמעט שחור (כותרת מוצר)
COLOR_SAMPLE         = "#d35400"   # כתום (זמן דוגמית)
COLOR_SOURCE         = "#aaa"      # אפור (מקור קובץ)
COLOR_MOQ_OK         = "#f1c40f"   # זהב (MOQ תקין)
COLOR_MOQ_NAN        = "#e74c3c"   # אדום (MOQ חסר)
COLOR_TAG_BG         = "#333"      # רקע תגיות קטגוריה
COLOR_CAPACITY_BG    = "#eee"      # רקע תגית נפח
COLOR_CAPACITY_TEXT  = "#333"      # טקסט תגית נפח
COLOR_SUCCESS        = "#219653"   # ירוק כהה (hover כפתור מייל)

# --- Font ---
FONT_MAIN = "'Arial', sans-serif"

# --- Card dimensions ---
CARD_HEIGHT       = "720px"   # הוגדל מעט כדי לאכלס את שורת השקלים
CARD_IMAGE_HEIGHT = "200px"

# --- Currency defaults ---
DEFAULT_USD_ILS = 3.65

# --- Category keyword map ---
CATEGORY_MAP = {
    "טכנולוגיה וגאדג'טים": ["usb", "power bank", "speaker", "charger", "cable", "wireless", "mouse", "earphone", "headphone", "bluetooth", "smart", "hub", "adapter"],
    "מחנאות, נופש וספורט": ["camp", "tent", "outdoor", "sport", "yoga", "fitness", "picnic", "beach", "towel", "mat", "flashlight", "jump rope", "bottle", "flask", "tumbler", "drinkware", "cooler"],
    "בקבוקים, כוסות ושתייה": ["bottle", "mug", "cup", "tumbler", "flask", "drinkware", "thermos", "shaker", "glass", "straw"],
    "עטים וכלי כתיבה": ["pen", "pencil", "notebook", "notepad", "stylus", "marker", "highlighter", "stationery", "diary"],
    "תיקים וארנקים": ["bag", "backpack", "tote", "pouch", "wallet", "drawstring", "duffel", "briefcase", "cooler", "luggage"],
    "טקסטיל וביגוד": ["shirt", "t-shirt", "cap", "hat", "jacket", "apron", "socks", "apparel", "wear"],
    "לבית ולמשרד": ["clock", "desk", "organizer", "frame", "lamp", "light", "home", "office", "mouse pad", "lanyard", "keychain"],
    "עונות (קיץ/חורף)": ["summer", "winter", "umbrella", "fan", "sunglasses", "ice", "warm", "blanket", "beanie", "scarf"],
    "אקולוגי וקיימות": ["eco", "bamboo", "wheat", "recycled", "cork", "sustainable", "rpet", "organic", "cotton", "biodegradable"]
}

# --- Keyword sets for parsing ---
PACKING_KEYWORDS  = ['OPP BAG', 'POLY BAG', 'PE BAG', 'PACKING', 'MEAS', 'CTN', 'G.W', 'N.W', 'BOX']
PRICE_KEYWORDS    = ['USD', 'PRICE']
PACKING_KEYS      = ['PACKING', 'OPP', 'BOX', 'CTN', 'MEAS', 'G.W', 'N.W', 'KGS']
DELIVERY_KEYS     = ['DELIVERY', 'DAYS', 'LEAD TIME', 'VALIDITY']
GENERAL_KEYS      = ['DATE', 'SOURCER', 'ITEM', 'DESCRIPTION']
SKIP_CONTENT_KEYS = ['WEB', 'HTTP', 'HTTPS', 'EXCHANGE RATE', 'FOB', 'PICTURE', 'PRODUCT DETAILS']
ITEM_TRIGGER_KEYS = ['ITEM NO', 'ITEM REF', 'ITEM:', '*ITEM', 'DESCRIPTION:', 'DESCRIPTION :']


# =============================================================================
# PAGE SETUP
# =============================================================================

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0
if 'last_filters' not in st.session_state:
    st.session_state.last_filters = None
# zoom dialog state: holds (img_b64, title) or None
if 'zoom_image' not in st.session_state:
    st.session_state.zoom_image = None


# =============================================================================
# CSS
# =============================================================================

st.markdown(f"""
<style>
html, body, [data-testid="stSidebar"], [data-testid="stSidebar"] *, .stText, p, h1, h2, h3, h4, h5, h6 {{
    font-family: {FONT_MAIN} !important;
}}
.material-icons, .stIcon, svg, i {{
    font-family: 'Material Icons' !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
    font-family: {FONT_MAIN} !important;
    font-weight: 700 !important;
}}
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header {{background-color: transparent !important;}}
[data-testid="stSidebarHeader"] {{
    display: none !important;
}}
section[data-testid="stSidebar"] .block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] .stMarkdown h2 {{
    font-family: {FONT_MAIN} !important;
    color: {COLOR_PRIMARY} !important;
    font-weight: 900 !important;
    font-size: 1.6rem !important;
    border-bottom: 3px solid {COLOR_SIDEBAR_BORDER} !important;
    padding-bottom: 6px !important;
    margin-bottom: 18px !important;
    margin-top: 0 !important;
    text-align: right !important;
    direction: rtl !important;
    width: 100%;
    display: block;
}}
section[data-testid="stSidebar"] label p {{
    font-family: {FONT_MAIN} !important;
    color: {COLOR_TEXT_DARK} !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    text-align: right !important;
    direction: rtl !important;
    width: 100%;
}}
[data-testid="stWidgetLabel"] p {{
    direction: rtl !important;
    text-align: right !important;
    font-family: {FONT_MAIN} !important;
}}
section[data-testid="stSidebar"] .stSlider > label,
section[data-testid="stSidebar"] .stNumberInput > label {{
    text-align: right !important;
    direction: rtl !important;
    display: block !important;
    width: 100% !important;
    font-family: {FONT_MAIN} !important;
}}
section[data-testid="stSidebar"] .stSlider input[type="range"],
section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {{
    direction: ltr !important;
}}
section[data-testid="stSidebar"] .stNumberInput input {{
    direction: ltr !important;
    text-align: left !important;
}}
.stMultiSelect {{
    position: relative !important;
    width: 100% !important;
    max-width: 100% !important;
}}
.stMultiSelect [data-baseweb="popover"] {{
    position: absolute !important;
    left: 0 !important;
    right: auto !important;
    width: fit-content !important;
    max-width: 280px !important;
    min-width: 200px !important;
    overflow: hidden !important;
    white-space: normal !important;
    word-break: break-word !important;
    box-sizing: border-box !important;
    z-index: 9999 !important;
}}
[data-testid="stVirtualDropdown"] {{
    position: absolute !important;
    left: 0 !important;
    right: auto !important;
    max-width: 280px !important;
    overflow: hidden !important;
}}
.stMultiSelect div[data-baseweb="select"] {{
    max-width: 100% !important;
    direction: rtl !important;
    width: 100% !important;
    position: relative !important;
    overflow: visible !important;
}}
.stMultiSelect [data-baseweb="select"] [role="option"] {{
    word-wrap: break-word !important;
    white-space: normal !important;
}}
.stSelectbox div[data-baseweb="select"] {{
    width: 100% !important;
    position: relative !important;
}}
.stSelectbox [data-baseweb="popover"] {{
    position: absolute !important;
    left: 0 !important;
    right: auto !important;
    max-width: 280px !important;
    overflow: hidden !important;
}}
.stTextInput > div > div > input {{
    font-family: {FONT_MAIN} !important;
    border-radius: 30px !important; border: 2px solid #eaeaea !important;
    padding: 15px 20px !important; font-size: 16px !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
    text-align: left !important;
    direction: ltr !important;
}}
.stTextInput > div > div > input:focus {{
    border-color: #111 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}}
div[data-testid="stVerticalBlock"] > div[style*="border"] {{
    border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    background-color: white; padding: 15px !important; position: relative;
    direction: ltr !important; text-align: left !important;
}}
div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {{
    transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.08) !important;
}}
.email-btn {{
    display: block; width: 100%; text-align: center; background-color: {COLOR_PRICE};
    color: white !important; padding: 10px; border-radius: 8px; text-decoration: none;
    font-weight: bold; margin-top: 20px; transition: background-color 0.3s;
    font-family: {FONT_MAIN} !important;
}}
.email-btn:hover {{ background-color: {COLOR_SUCCESS}; }}
/* כפתור זום תמונה */
.zoom-btn {{
    display: block; width: 100%; text-align: center; background: none;
    border: 1px dashed #ccc; border-radius: 6px; padding: 2px 0;
    cursor: pointer; font-size: 11px; color: #999; margin-top: 4px;
}}
.zoom-btn:hover {{ border-color: #7C3AED; color: #7C3AED; }}
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 10px; }}
::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 10px; }}
::-webkit-scrollbar-thumb:hover {{ background: #999; }}
html, body {{
    overflow-x: hidden !important;
    max-width: 100vw !important;
}}
.main, .block-container {{
    overflow-x: hidden !important;
    max-width: 100% !important;
}}
main {{
    overflow-x: hidden !important;
    max-width: 100vw !important;
}}
* {{
    max-width: 100% !important;
    box-sizing: border-box !important;
}}
.sticky-cart {{
    position: sticky;
    bottom: 0;
    z-index: 100;
    background: #f8fafc;
    box-shadow: 0 -2px 12px rgba(0,0,0,0.07);
    padding-bottom: 18px;
    margin-bottom: 0;
    border-radius: 0 0 16px 16px;
    transition: box-shadow 0.2s;
}}
.sticky-cart .email-btn {{
    margin-bottom: 0;
}}
</style>
""", unsafe_allow_html=True)


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
        if num >= 1000:
            return f"{num/1000:g}K"
        return f"{num:g}"
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
    """Extract sourcer/buyer name from lines containing SOURCER keyword."""
    for detail in details_list:
        if 'SOURCER' in detail.upper():
            # Support formats: "SOURCER: NANA", "SOURCER NANA", "SOURCER:NANA"
            match = re.search(r'SOURCER\s*:?\s*([A-Za-z\u0590-\u05FF]+)', detail, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()
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

    if re.search(r'\b(soccer|football|כדורגל|basketball|tennis|כדורסל|טניס|volleyball|כדורעף|ping pong|table tennis|פינג פונג)\b', text_to_scan):
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
                    if val > 0:
                        prices.append(val)
                except:
                    pass
    return min(prices) if prices else None


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
    materials = []
    text_lower = full_text.lower()
    if 'stainless' in text_lower or '304' in text_lower or '316' in text_lower:
        materials.append('Stainless Steel')
    if 'plastic' in text_lower or re.search(r'\bpp\b', text_lower) or 'tritan' in text_lower:
        materials.append('Plastic')
    if 'bamboo' in text_lower:
        materials.append('Bamboo')
    if 'glass' in text_lower:
        materials.append('Glass')
    if 'silicone' in text_lower:
        materials.append('Silicone')
    if 'ceramic' in text_lower:
        materials.append('Ceramic')
    return list(set(materials))


def transform_he_to_en(text):
    he_en_map = {
        'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g',
        'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n',
        'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u',
        'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y'
    }
    return "".join(he_en_map.get(char, char) for char in text.lower())


def normalize_text(text):
    """Normalize text for search: lowercase, keep alphanumeric + Hebrew + spaces."""
    if not isinstance(text, str):
        text = str(text)
    # שומרים רווחים כדי שנוכל להפריד בין מילים בחיפוש
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF ]', ' ', text).lower()


def classify_details(display_list):
    """Split a product's display_list into labeled buckets for rendering."""
    general_info, price_info, packing_info = [], [], []
    delivery_info, sample_info, other_info = [], [], []

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


def compute_ils_prices(price_info_lines, usd_ils_rate):
    """
    From a list of price strings, extract all USD values and return
    a list of formatted ILS strings (one per detected price).
    Returns empty list if rate is 0 or no prices found.
    """
    if not usd_ils_rate or usd_ils_rate <= 0:
        return []
    ils_lines = []
    for line in price_info_lines:
        values = re.findall(r'\d*\.\d+|\d+', line)
        for v in values:
            try:
                usd = float(v)
                if 0 < usd < 10000:   # סינון ערכים סבירים
                    ils = usd * usd_ils_rate
                    ils_lines.append(f"₪ {ils:.2f}")
            except:
                pass
    return ils_lines


# =============================================================================
# GOOGLE DRIVE SERVICE & DATA LOADING
# =============================================================================

def get_gdrive_service():
    try:
        encoded_key = constants.GCP_SERVICE_ACCOUNT
        decoded_key = base64.b64decode(encoded_key).decode('utf-8')
        info = json.loads(decoded_key)
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
        includeItemsFromAllDrives=True
    ).execute()

    all_products = []

    for item in results.get('files', []):
        try:
            request = service.files().get_media(fileId=item['id'], supportsAllDrives=True)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            df_file = pd.read_excel(fh, header=None, engine='xlrd' if item['name'].endswith('.xls') else None)

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

                        if offset > 1 and any(k in line.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', '*ITEM']):
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
                        all_products.append({
                            'item_key':        item_key if item_key else details[0],
                            'display_list':    details,
                            'full_text':       full_text_str,
                            'normalized_text': normalize_text(full_text_str),
                            'file_source':     item['name'],
                            'base_filename':   item['name'].rsplit('.', 1)[0],
                            'row_index':       idx,
                            'min_price':       extract_min_price(details),
                            'moq':             extract_moq(details),
                            'delivery_days':   extract_delivery_days(details),
                            'capacity':        extract_capacity(full_text_str),
                            'materials':       extract_materials(full_text_str),
                            'categories':      extract_categories(details),
                            'sourcer':         extract_sourcer(details),        # ← חדש
                        })
        except:
            continue

    img_results = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map


# =============================================================================
# UI COMPONENTS
# =============================================================================

def _resolve_image_id(row, i, img_map):
    """Find the best matching image ID for a product row."""
    base_name_clean = normalize_text(row['base_filename'])
    valid_images = {name: img_id for name, img_id in img_map.items()
                    if base_name_clean in normalize_text(name)}
    if not valid_images:
        return None
    row_target = f"row_{row['row_index']}"
    for name, img_id in valid_images.items():
        if row_target in normalize_text(name):
            return img_id
    return list(valid_images.values())[i % len(valid_images)]


def _build_tags_html(row):
    """Build the colored tag strip (MOQ, capacity, categories)."""
    moq_val = format_moq_display(row['moq'])
    if moq_val == "NAN":
        moq_tag = (
            f"<span style='background:{COLOR_MOQ_NAN}; color:#fff; padding:3px 8px; "
            f"border-radius:4px; font-size:11px; font-weight:bold; white-space:nowrap;'>📦 MOQ: NAN</span>"
        )
    else:
        moq_tag = (
            f"<span style='background:{COLOR_MOQ_OK}; color:#000; padding:3px 8px; "
            f"border-radius:4px; font-size:11px; font-weight:bold; white-space:nowrap;'>📦 MOQ: {moq_val}</span>"
        )

    capacity_tag = ""
    if row['capacity']:
        capacity_tag = (
            f"<span style='background:{COLOR_CAPACITY_BG}; color:{COLOR_CAPACITY_TEXT}; padding:3px 8px; "
            f"border-radius:4px; font-size:11px; white-space:nowrap;'>💧 {row['capacity']}</span>"
        )

    # תגית איש רכש
    sourcer_tag = ""
    if row.get('sourcer'):
        sourcer_tag = (
            f"<span style='background:#e0e7ff; color:#3730a3; padding:3px 8px; "
            f"border-radius:4px; font-size:11px; white-space:nowrap;'>👤 {row['sourcer']}</span>"
        )

    category_tags = "".join(
        f"<span style='background:{COLOR_TAG_BG}; color:#fff; padding:3px 8px; "
        f"border-radius:4px; font-size:11px; white-space:nowrap;'>🏷️ {cat}</span>"
        for cat in (row['categories'] or [])
    )

    return (
        f"<div style='display:flex; flex-wrap:wrap; gap:5px; margin-bottom:5px; direction:ltr;'>"
        f"{moq_tag}{capacity_tag}{sourcer_tag}{category_tags}</div>"
    )


# --- Image zoom dialog ---
@st.dialog("🔍 תצוגה מוגדלת")
def _show_zoom_dialog(img_b64, title):
    """Dialog that shows a full-size zoomable image via st.image."""
    st.caption(title)
    img_bytes = base64.b64decode(img_b64)
    st.image(img_bytes, use_container_width=True)


def render_product_card(row, i, img_map, usd_ils_rate):
    """Render a single product card inside a Streamlit container."""
    unique_item_id = f"{row['base_filename']}_{row['row_index']}"

    with st.container(border=True):
        # --- Checkbox ---
        is_selected = unique_item_id in st.session_state.selected_items
        if st.checkbox("➕ בחר לשליחה", value=is_selected, key=f"chk_{unique_item_id}"):
            if not is_selected:
                st.session_state.selected_items[unique_item_id] = row.to_dict()
                st.rerun()
        else:
            if is_selected:
                del st.session_state.selected_items[unique_item_id]
                st.rerun()

        # --- Image ---
        img_id  = _resolve_image_id(row, i, img_map)
        img_b64 = get_image_base64(img_id) if img_id else None

        if img_b64:
            img_bytes = base64.b64decode(img_b64)
            st.image(img_bytes, use_container_width=True)
            # כפתור זום קטן מתחת לתמונה
            if st.button("🔍 הגדל תמונה", key=f"zoom_{unique_item_id}", use_container_width=True):
                _show_zoom_dialog(img_b64, row['item_key'])
        else:
            st.markdown(
                f'<div style="height:{CARD_IMAGE_HEIGHT}; display:flex; justify-content:center; '
                f'align-items:center; background:#f9f9f9; border-radius:8px; color:#aaa; font-size:12px;">'
                f'📷 לא נמצאה תמונה</div>',
                unsafe_allow_html=True
            )

        # --- Tags ---
        tags_html = _build_tags_html(row)
        st.markdown(tags_html, unsafe_allow_html=True)

        # --- Details ---
        general_info, price_info, packing_info, delivery_info, sample_info, other_info = classify_details(row['display_list'])

        details_html = '<div style="flex-grow:1; overflow-y:auto; text-align:left; line-height:1.5; padding-right:5px; direction:ltr;">'

        for info in general_info:
            details_html += f"<div style='font-weight:800; font-size:14px; color:{COLOR_GENERAL}; margin-bottom:5px;'>{info}</div>"
        for info in sample_info:
            details_html += f"<div style='font-size:13px; color:{COLOR_SAMPLE}; font-weight:700; margin-bottom:3px;'>⏱️ {info}</div>"
        for info in delivery_info:
            details_html += f"<div style='font-size:13px; color:{COLOR_DELIVERY}; font-weight:600; margin-bottom:2px;'>🚚 {info}</div>"
        for info in packing_info:
            details_html += f"<div style='font-size:13px; color:{COLOR_PACKING}; margin-bottom:2px;'>📦 {info}</div>"
        for info in other_info:
            details_html += f"<div style='font-size:12px; color:{COLOR_OTHER};'>• {info}</div>"

        details_html += '</div>'

        # --- Price footer ---
        price_footer = (
            f'<div style="flex-shrink:0; margin-top:8px; border-top:1px solid #eee; '
            f'padding-top:8px; text-align:left; direction:ltr;">'
        )

        # מחיר USD
        for info in price_info:
            price_footer += (
                f"<div style='color:{COLOR_PRICE}; font-weight:900; font-size:15px; "
                f"margin-bottom:2px; line-height:1.2;'>💰 {info}</div>"
            )

        # מחיר ILS — מחושב ומוצג בסגול
        ils_values = compute_ils_prices(price_info, usd_ils_rate)
        if ils_values:
            ils_joined = "  |  ".join(ils_values)
            price_footer += (
                f"<div style='color:{COLOR_PRICE_ILS}; font-weight:800; font-size:14px; "
                f"margin-bottom:4px; line-height:1.3;'>🪙 {ils_joined}</div>"
            )

        price_footer += (
            f"<div style='font-size:10px; color:{COLOR_SOURCE}; margin-top:4px; white-space:nowrap; "
            f"overflow:hidden; text-overflow:ellipsis;'>📂 {row['file_source']}</div>"
            '</div>'
        )

        st.markdown(details_html + price_footer, unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

def _render_cart_section():
    """Render the selected-items cart inside the sidebar."""
    st.header("🛒 מוצרים לשליחה")

    if not st.session_state.selected_items:
        st.info("לא נבחרו מוצרים עדיין.")
        return

    st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")

    email_body = "שלום,\n\nלהלן פרטי המוצרים לבקשתך:\n\n"
    for item_data in st.session_state.selected_items.values():
        email_body += f"--- {item_data['item_key']} ---\n"
        for detail in item_data['display_list']:
            if "Unnamed" not in detail and not contains_chinese(detail) and "MOQ" not in detail.upper():
                email_body += f"• {detail}\n"
        email_body += f"מקור: {item_data['file_source']}\n\n"
    email_body += "בברכה,\nNext Design"

    encoded_subject = urllib.parse.quote("Next Design - פרטי מוצרים")
    encoded_body    = urllib.parse.quote(email_body)
    st.markdown(
        f'<a href="mailto:?subject={encoded_subject}&body={encoded_body}" class="email-btn" target="_blank">'
        f'✉️ שלח במייל עכשיו</a>',
        unsafe_allow_html=True
    )

    if st.button("🗑️ נקה רשימה", use_container_width=True):
        st.session_state.selected_items = {}


def render_sidebar(df):
    """
    Render the full sidebar (filters, currency, cart, refresh).
    Returns a dict of active filter values + usd_ils_rate.
    """
    with st.sidebar:
        st.header("⚙️ סינון חכם")

        # --- קטגוריות ---
        selected_categories = st.multiselect(
            "קטגוריה (Category)", list(CATEGORY_MAP.keys()), placeholder="בחר קטגוריות..."
        )

        # --- מחיר ---
        price_min, price_max = st.slider(
            "טווח מחיר ליח' (USD)", min_value=0.0, max_value=200.0, value=(0.0, 200.0), step=0.1
        )

        # --- שער דולר ---
        usd_ils_rate = st.number_input(
            "שער דולר (USD/ILS ₪)",
            min_value=0.0,
            value=DEFAULT_USD_ILS,
            step=0.01,
            format="%.2f",
            help="המחיר בשקלים בכרטיסיות יחושב לפי שער זה"
        )

        # --- MOQ ---
        max_moq = st.number_input(
            "MOQ מקסימלי (כמות מינימלית)", min_value=0, value=None, placeholder="ללא הגבלה...", step=500
        )

        # --- זמן אספקה ---
        max_delivery = st.slider("זמן אספקה מקסימלי (ימים)", min_value=5, max_value=90, value=90, step=5)

        # --- חומר ונפח ---
        available_capacities = sorted([c for c in df['capacity'].unique() if c]) if not df.empty else []
        selected_materials   = st.multiselect(
            "חומר (Material)",
            ["Stainless Steel", "Plastic", "Bamboo", "Glass", "Silicone", "Ceramic"],
            placeholder="בחר חומרים..."
        )
        selected_capacities  = st.multiselect(
            "נפח (Capacity)", available_capacities, placeholder="בחר נפחים (למשל 500ml)..."
        )

        # --- ספקים (קבצי מקור) ---
        available_sources = sorted(df['file_source'].dropna().unique().tolist()) if not df.empty else []
        selected_sources  = st.multiselect(
            "ספק / קובץ מקור", available_sources, placeholder="בחר ספקים..."
        )

        # --- אנשי רכש (sourcers) ---
        available_sourcers = sorted([
            s for s in df['sourcer'].dropna().unique().tolist() if s
        ]) if not df.empty else []
        selected_sourcers  = st.multiselect(
            "איש רכש (Sourcer)", available_sourcers, placeholder="בחר איש רכש..."
        )

        st.divider()
        _render_cart_section()
        st.divider()

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
        selected_sources=selected_sources,
        selected_sourcers=selected_sourcers,
    )


# =============================================================================
# PAGE HEADER
# =============================================================================

def render_page_header():
    """Render the top branding header."""
    st.markdown("""
        <div style="text-align:center; margin-bottom:40px; margin-top:10px; direction:rtl;">
            <a href="https://nextd.wallak.co.il/" target="_blank" style="text-decoration:none;">
                <h1 style="font-family:'Arial',sans-serif; font-weight:900; letter-spacing:1px; color:#000; font-size:46px; margin-bottom:0;">
                    <span style="background-color:#000; color:#fff; padding:0 12px; border-radius:6px; margin-right:5px;">NEXT</span>DESIGN
                </h1>
            </a>
            <h3 style="font-family:'Arial',sans-serif; color:#666; font-weight:500; margin-top:5px;">קטלוג הצעות מחיר ביבוא 🔎</h3>
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# PAGINATION
# =============================================================================

def render_pagination(total_products):
    """Render prev/next pagination controls and update session state."""
    st.markdown("<br>", unsafe_allow_html=True)
    total_pages  = (total_products + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE
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
            unsafe_allow_html=True
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
    """Return a filtered and deduplicated DataFrame based on all active filters."""
    results = df.copy()

    # --- חיפוש חופשי מתקדם: AND על מילים ---
    query = search_input.strip()
    if query and query.upper() != "ALL":
        raw_words = query.split()
        for word in raw_words:
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

    # --- סינון ספק ---
    if filters['selected_sources']:
        results = results[results['file_source'].isin(filters['selected_sources'])]

    # --- סינון איש רכש ---
    if filters['selected_sourcers']:
        results = results[results['sourcer'].isin(filters['selected_sourcers'])]

    return results.drop_duplicates(subset=['item_key', 'file_source'])


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    render_page_header()

    # טעינת נתונים פעם אחת בלבד
    if 'df' not in st.session_state or 'img_map' not in st.session_state:
        st.session_state.df, st.session_state.img_map = load_all_data()

    df      = st.session_state.df
    img_map = st.session_state.img_map

    # סיידבר — מחזיר dict של כל ערכי הסינון
    filters = render_sidebar(df)

    # שורת חיפוש
    search_input = st.text_input("", placeholder="🔍 הקלד שם מוצר לחיפוש (או ALL להצגת כל הקטלוג)...")

    should_show = (
        bool(search_input.strip()) or
        bool(filters['selected_categories']) or
        bool(filters['selected_materials']) or
        bool(filters['selected_capacities']) or
        bool(filters['selected_sources']) or
        bool(filters['selected_sourcers'])
    )
    if df.empty or not should_show:
        return

    # סינון
    results = apply_filters(df, search_input, filters)

    if results.empty:
        st.warning("לא נמצאו תוצאות התואמות לחיפוש ולסינונים שלך.")
        return

    # איפוס עמוד בעת שינוי סינון
    current_filters = (
        search_input,
        tuple(filters['selected_categories']),
        filters['price_min'], filters['price_max'],
        filters['max_moq'], filters['max_delivery'],
        tuple(filters['selected_materials']),
        tuple(filters['selected_capacities']),
        tuple(filters['selected_sources']),
        tuple(filters['selected_sourcers']),
    )
    if st.session_state.last_filters != current_filters:
        st.session_state.current_page = 0
        st.session_state.last_filters = current_filters

    # Pagination
    total_products = len(results)
    start          = st.session_state.current_page * PRODUCTS_PER_PAGE
    end            = min(start + PRODUCTS_PER_PAGE, total_products)
    page_results   = results.iloc[start:end]

    # גריד מוצרים
    st.write("<br>", unsafe_allow_html=True)
    cols = st.columns(COLUMNS_PER_ROW)
    for i, (_, row) in enumerate(page_results.iterrows()):
        with cols[i % COLUMNS_PER_ROW]:
            render_product_card(row, i, img_map, filters['usd_ils_rate'])

    render_pagination(total_products)


if __name__ == "__main__" or True:
    main()
