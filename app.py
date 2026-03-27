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
import constants  # <--- חיבור לקובץ ה-Base64 שלך

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

# --- הגדרות קבועות (מעודכן לכונן משותף) ---
FOLDER_ID_EXCELS = "1x7bE0YmGhrK_-0f06ixwlOKqquV_8AHZ"
FOLDER_ID_IMAGES = "1R4nm5cf2NEWB30IceF4cL5oShNlqurPS"

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}

# --- מילון קטגוריות (חדש) ---
CATEGORY_MAP = {
    "טכנולוגיה וגאדג'טים": ["usb", "power bank", "speaker", "charger", "cable", "wireless", "mouse", "earphone", "headphone", "bluetooth", "smart", "hub", "adapter"],
    "מחנאות, נופש וספורט": ["camp", "tent", "outdoor", "sport", "yoga", "fitness", "picnic", "beach", "towel", "mat", "flashlight", "jump rope"],
    "בקבוקים, כוסות ושתייה": ["bottle", "mug", "cup", "tumbler", "flask", "drinkware", "thermos", "shaker", "glass", "straw"],
    "עטים וכלי כתיבה": ["pen", "pencil", "notebook", "notepad", "stylus", "marker", "highlighter", "stationery", "diary"],
    "תיקים וארנקים": ["bag", "backpack", "tote", "pouch", "wallet", "drawstring", "duffel", "briefcase", "cooler", "luggage"],
    "טקסטיל וביגוד": ["shirt", "t-shirt", "cap", "hat", "jacket", "apron", "socks", "apparel", "wear"],
    "לבית ולמשרד": ["clock", "desk", "organizer", "frame", "lamp", "light", "home", "office", "mouse pad", "lanyard", "keychain"],
    "עונות (קיץ/חורף)": ["summer", "winter", "umbrella", "fan", "sunglasses", "ice", "warm", "blanket", "beanie", "scarf"],
    "אקולוגי וקיימות": ["eco", "bamboo", "wheat", "recycled", "cork", "sustainable", "rpet", "organic", "cotton", "biodegradable"]
}

# --- עיצוב CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px; }
    
    .stTextInput > div > div > input {
        border-radius: 30px !important; border: 2px solid #eaeaea !important;
        padding: 15px 20px !important; font-size: 16px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #111 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    }

    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        background-color: white; padding: 15px !important; position: relative;
    }
    div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {
        transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.08) !important;
    }
    
    .email-btn {
        display: block; width: 100%; text-align: center; background-color: #27ae60;
        color: white !important; padding: 10px; border-radius: 8px; text-decoration: none;
        font-weight: bold; margin-top: 20px; transition: background-color 0.3s;
    }
    .email-btn:hover { background-color: #219653; }
    
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 10px; }
    ::-webkit-scrollbar-thumb { background: #ccc; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #999; }
    </style>
""", unsafe_allow_html=True)

# --- כותרת ---
st.markdown("""
    <div style="text-align: center; margin-bottom: 40px; margin-top: 10px;">
        <a href="https://nextd.wallak.co.il/" target="_blank" style="text-decoration: none;">
            <h1 style="font-family: 'Arial', sans-serif; font-weight: 900; letter-spacing: 1px; color: #000; font-size: 46px; margin-bottom: 0;">
                <span style="background-color: #000; color: #fff; padding: 0 12px; border-radius: 6px; margin-right: 5px;">NEXT</span>DESIGN
            </h1>
        </a>
        <h3 style="color: #666; font-weight: 400; margin-top: 5px; font-family: 'Arial', sans-serif;">קטלוג חכם לסוכנים 🔎</h3>
    </div>
""", unsafe_allow_html=True)

# --- פונקציות ---
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_min_price(details_list):
    prices = []
    for detail in details_list:
        d_up = detail.upper()
        if 'USD' in d_up or 'PRICE' in d_up or '$' in d_up:
            matches = re.findall(r'\d*\.\d+|\d+', detail)
            for match in matches:
                try:
                    val = float(match)
                    if val > 0: prices.append(val)
                except: pass
    return min(prices) if prices else None

def extract_moq(details_list):
    for detail in details_list:
        d_up = detail.upper()
        if 'MOQ' in d_up:
            nums = re.findall(r'\d+', detail.replace(',', ''))
            if nums: return int(nums[0])
    return None

def extract_delivery_days(details_list):
    for detail in details_list:
        d_up = detail.upper()
        if 'DELIVERY' in d_up or 'DAYS' in d_up or 'LEAD TIME' in d_up:
            if 'SAMPLE' not in d_up:
                nums = re.findall(r'\d+', detail)
                if nums: return max([int(n) for n in nums])
    return None

def extract_capacity(full_text):
    matches = re.findall(r'(\d{2,4})\s*(ml|oz)', full_text.lower())
    if matches: return f"{matches[0][0]}{matches[0][1]}"
    return None

def extract_materials(full_text):
    materials = []
    text_lower = full_text.lower()
    if 'stainless' in text_lower or '304' in text_lower or '316' in text_lower: materials.append('Stainless Steel')
    if 'plastic' in text_lower or re.search(r'\bpp\b', text_lower) or 'tritan' in text_lower: materials.append('Plastic')
    if 'bamboo' in text_lower: materials.append('Bamboo')
    if 'glass' in text_lower: materials.append('Glass')
    if 'silicone' in text_lower: materials.append('Silicone')
    if 'ceramic' in text_lower: materials.append('Ceramic')
    return list(set(materials))

# --- פונקציה חדשה: חילוץ קטגוריות ---
def extract_categories(full_text):
    found_categories = []
    text_lower = full_text.lower()
    for cat, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            # שימוש ב- \b מבטיח שנחפש מילה שלמה. למשל 'pen' לא יתפוס 'open'
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                found_categories.append(cat)
                break
    return found_categories

def transform_he_to_en(text):
    he_en_map = {'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g', 'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n', 'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u', 'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y', 'ז': 'z'}
    return "".join([he_en_map.get(char, char) for char in text.lower()])

def normalize_text(text):
    if not isinstance(text, str): text = str(text)
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '', text).lower()

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
def get_image_base64(_service, file_id):
    try:
        request = _service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except: return None

@st.cache_data(ttl=600)
def load_all_data():
    service = get_gdrive_service()
    if not service: return pd.DataFrame(), {}
    
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
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df_file = pd.read_excel(fh, header=None, engine='xlrd' if item['name'].endswith('.xls') else None)
            
            skip_until = -1
            for idx in range(len(df_file)):
                if idx < skip_until: continue
                
                row_str = " ".join(df_file.iloc[idx].dropna().astype(str))
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', '*ITEM', 'DESCRIPTION:', 'DESCRIPTION :']):
                    details = []
                    item_key = ""
                    for offset in range(25):
                        curr_idx = idx + offset
                        if curr_idx >= len(df_file): skip_until = curr_idx; break
                            
                        b_row = df_file.iloc[curr_idx].dropna().astype(str)
                        line = " ".join(b_row).strip()
                        line = re.sub(r'\s+', ' ', line)
                        
                        if offset > 1 and any(k in line.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', '*ITEM']):
                            skip_until = curr_idx; break
                        
                        if line and not any(x in line.upper() for x in ['WEB', 'HTTP', 'HTTPS', 'EXCHANGE RATE', 'FOB', 'PICTURE', 'PRODUCT DETAILS']):
                            details.append(line)
                            if 'ITEM' in line.upper() and not item_key: item_key = line
                    else: skip_until = idx + 25

                    if details:
                        full_text_str = " ".join(details)
                        all_products.append({
                            'item_key': item_key if item_key else details[0],
                            'display_list': details,
                            'full_text': full_text_str,
                            'normalized_text': normalize_text(full_text_str),
                            'file_source': item['name'],
                            'base_filename': item['name'].rsplit('.', 1)[0],
                            'row_index': idx,
                            'min_price': extract_min_price(details),
                            'moq': extract_moq(details),
                            'delivery_days': extract_delivery_days(details),
                            'capacity': extract_capacity(full_text_str),
                            'materials': extract_materials(full_text_str),
                            'categories': extract_categories(full_text_str) # --- התוספת לתיוג הקטגוריות ---
                        })
        except: continue
    
    img_results = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents", 
        fields="files(id, name)",
        supportsAllDrives=True, 
        includeItemsFromAllDrives=True
    ).execute()
    
    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map

df, img_map = load_all_data()

# --- תפריט צד ---
with st.sidebar:
    st.header("⚙️ סינון חכם")
    
    # --- הפילטר החדש של הקטגוריות ---
    available_categories = list(CATEGORY_MAP.keys())
    selected_categories = st.multiselect("קטגוריה (Category)", available_categories, placeholder="בחר קטגוריות...")
    
    price_min, price_max = st.slider("טווח מחיר ליח' (USD)", min_value=0.0, max_value=30.0, value=(0.0, 30.0), step=0.1)
    max_moq = st.number_input("MOQ מקסימלי (כמות מינימלית)", min_value=0, value=None, placeholder="ללא הגבלה...", step=500)
    max_delivery = st.slider("זמן אספקה מקסימלי (ימים)", min_value=5, max_value=90, value=90, step=5)
    
    available_materials = ["Stainless Steel", "Plastic", "Bamboo", "Glass", "Silicone", "Ceramic"]
    available_capacities = sorted([c for c in df['capacity'].unique() if c]) if not df.empty else []
    
    selected_materials = st.multiselect("חומר (Material)", available_materials, placeholder="בחר חומרים...")
    selected_capacities = st.multiselect("נפח (Capacity)", available_capacities, placeholder="בחר נפחים (למשל 500ml)...")
    
    st.divider()
    st.header("🛒 מוצרים לשליחה")
    if not st.session_state.selected_items:
        st.info("לא נבחרו מוצרים עדיין.")
    else:
        st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")
        email_body = "שלום,\n\nלהלן פרטי המוצרים לבקשתך:\n\n"
        for item_id, item_data in st.session_state.selected_items.items():
            email_body += f"--- {item_data['item_key']} ---\n"
            for detail in item_data['display_list']:
                if "Unnamed" not in detail and not contains_chinese(detail): 
                    email_body += f"• {detail}\n"
            email_body += f"מקור: {item_data['file_source']}\n\n"
        email_body += "בברכה,\nNext Design"
        encoded_subject = urllib.parse.quote("Next Design - פרטי מוצרים")
        encoded_body = urllib.parse.quote(email_body)
        st.markdown(f'<a href="mailto:?subject={encoded_subject}&body={encoded_body}" class="email-btn" target="_blank">✉️ שלח במייל עכשיו</a>', unsafe_allow_html=True)
        if st.button("🗑️ נקה רשימה", use_container_width=True):
            st.session_state.selected_items = {}
            st.rerun()

# --- חיפוש ותצוגה ---
search_input = st.text_input("", placeholder="🔍 הקלד שם מוצר לחיפוש (או ALL להצגת כל הקטלוג)...")

if not df.empty and search_input:
    service = get_gdrive_service()
    
    if search_input.strip().upper() == "ALL":
        results = df.copy()
    else:
        term = normalize_text(search_input)
        term_trans = normalize_text(transform_he_to_en(search_input))
        results = df[df['normalized_text'].str.contains(term, na=False) | df['normalized_text'].str.contains(term_trans, na=False)].copy()
    
    if not results.empty:
        # --- לוגיקת הסינון החדשה של קטגוריות ---
        if selected_categories: results = results[results['categories'].apply(lambda cats: any(c in cats for c in selected_categories))]
        
        if price_min > 0.0 or price_max < 30.0: results = results[results['min_price'].apply(lambda x: x is not None and price_min <= x <= price_max)]
        if max_moq is not None: results = results[results['moq'].apply(lambda x: x is None or x <= max_moq)]
        if max_delivery < 90: results = results[results['delivery_days'].apply(lambda x: x is not None and x <= max_delivery)]
        if selected_materials: results = results[results['materials'].apply(lambda x: any(m in x for m in selected_materials))]
        if selected_capacities: results = results[results['capacity'].isin(selected_capacities)]
    
    if not results.empty:
        results = results.drop_duplicates(subset=['item_key', 'file_source'])
        st.write("<br>", unsafe_allow_html=True)
        cols = st.columns(4)
        
        for i, (_, row) in enumerate(results.iterrows()):
            unique_item_id = f"{row['base_filename']}_{row['row_index']}"
            with cols[i % 4]:
                with st.container(border=True):
                    is_selected = unique_item_id in st.session_state.selected_items
                    
                    if st.checkbox("➕ בחר לשליחה", value=is_selected, key=f"chk_{unique_item_id}"):
                        if not is_selected:
                            st.session_state.selected_items[unique_item_id] = row
                            st.rerun()
                    else:
                        if is_selected:
                            del st.session_state.selected_items[unique_item_id]
                            st.rerun()
                    
                    img_id = None
                    base_name_clean = normalize_text(row['base_filename'])
                    valid_images = {name: i_id for name, i_id in img_map.items() if base_name_clean in normalize_text(name)}
                    if valid_images:
                        row_target = f"row_{row['row_index']}"
                        for name, i_id in valid_images.items():
                            if row_target in normalize_text(name): img_id = i_id; break
                        if not img_id: img_id = list(valid_images.values())[i % len(valid_images)]
                    
                    if img_id:
                        img_b64 = get_image_base64(service, img_id)
                        if img_b64:
                            img_html = f'<img src="data:image/jpeg;base64,{img_b64}" style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 4px;">'
                        else:
                            img_html = '<div style="color:#aaa; font-size:12px;">📷 לא נמצאה תמונה</div>'
                    else:
                        img_html = '<div style="color:#aaa; font-size:12px;">📷 לא נמצאה תמונה</div>'
                    
                    tags_html = ""
                    if row['moq']: tags_html += f"<span style='background:#f1c40f; color:#000; padding:2px 6px; border-radius:4px; font-size:11px; margin-right:4px; font-weight:bold; white-space: nowrap;'>📦 MOQ: {row['moq']}</span>"
                    if row['capacity']: tags_html += f"<span style='background:#eee; padding:2px 6px; border-radius:4px; font-size:11px; margin-right:4px; white-space: nowrap;'>💧 {row['capacity']}</span>"
                    if row['materials']: tags_html += f"<span style='background:#eee; padding:2px 6px; border-radius:4px; font-size:11px; margin-right:4px; white-space: nowrap;'>🛠️ {', '.join(row['materials'])}</span>"
                    
                    # --- הצגת תגיות הקטגוריה על המוצר ---
                    if row['categories']: tags_html += f"<span style='background:#d1d8e0; padding:2px 6px; border-radius:4px; font-size:11px; margin-right:4px; white-space: nowrap;'>🏷️ {', '.join(row['categories'])}</span>"

                    general_info, price_info, packing_info, delivery_info, sample_info, other_info = [], [], [], [], [], []
                    for detail in row['display_list']:
                        if contains_chinese(detail): continue
                        
                        d_up = detail.upper()
                        if 'USD' in d_up or 'PRICE' in d_up: price_info.append(detail)
                        elif any(x in d_up for x in ['PACKING', 'OPP', 'BOX', 'CTN', 'MEAS', 'G.W', 'N.W', 'KGS']): packing_info.append(detail)
                        elif 'SAMPLE' in d_up and any(x in d_up for x in ['TIME', 'DAY', 'LEAD']): sample_info.append(detail)
                        elif any(x in d_up for x in ['DELIVERY', 'DAYS', 'LEAD TIME', 'VALIDITY']): delivery_info.append(detail)
                        elif any(x in d_up for x in ['DATE', 'SOURCER', 'ITEM', 'DESCRIPTION']): general_info.append(detail)
                        else: other_info.append(detail)
                    
                    html_content = '<div style="display: flex; flex-direction: column; height: 620px;">'
                    html_content += f'<div style="height: 220px; display: flex; justify-content: center; align-items: center; margin-bottom: 10px; background-color: #fff; flex-shrink: 0;">{img_html}</div>'
                    html_content += f'<div style="min-height: 30px; text-align: left; margin-bottom: 5px; flex-shrink: 0;">{tags_html}</div>'
                    html_content += '<div style="flex-grow: 1; overflow-y: auto; text-align: left; font-family: sans-serif; line-height: 1.5; padding-right: 5px;">'
                    for info in general_info: html_content += f"<div style='font-weight: 800; font-size: 14px; color: #222; margin-bottom: 5px;'>{info}</div>"
                    for info in sample_info: html_content += f"<div style='font-size: 13px; color: #d35400; font-weight: 700; margin-bottom: 3px;'>⏱️ {info}</div>"
                    for info in delivery_info: html_content += f"<div style='font-size: 13px; color: #444; font-weight: 600; margin-bottom: 2px;'>🚚 {info}</div>"
                    for info in packing_info: html_content += f"<div style='font-size: 13px; color: #666; margin-bottom: 2px;'>📦 {info}</div>"
                    for info in other_info: html_content += f"<div style='font-size: 12px; color: #888;'>• {info}</div>"
                    html_content += '</div>'
                    html_content += '<div style="flex-shrink: 0; margin-top: 10px; border-top: 1px solid #eee; padding-top: 10px; text-align: left;">'
                    for info in price_info: html_content += f"<div style='color: #27ae60; font-weight: 900; font-size: 15px; margin-bottom: 3px; line-height: 1.2;'>💰 {info}</div>"
                    html_content += f"<div style='font-size: 10px; color: #aaa; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>📂 {row['file_source']}</div>"
                    html_content += '</div></div>'
                    
                    st.markdown(html_content, unsafe_allow_html=True)
    else:
        st.warning("לא נמצאו תוצאות התואמות לחיפוש ולסינונים שלך.")
