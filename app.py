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

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

# --- הגדרות קבועות (מעודכן לכונן משותף) ---
FOLDER_ID_EXCELS = "1x7bE0YmGhrK_-0f06ixwlOKqquV_8AHZ"
FOLDER_ID_IMAGES = "1R4nm5cf2NEWB30IceF4cL5oShNlqurPS"

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}

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
    .email-btn {
        display: block; width: 100%; text-align: center; background-color: #27ae60;
        color: white !important; padding: 10px; border-radius: 8px; text-decoration: none;
        font-weight: bold; margin-top: 20px;
    }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        background-color: white; padding: 15px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- כותרת ---
st.markdown("""
    <div style="text-align: center; margin-bottom: 40px; margin-top: 10px;">
        <a href="https://nextd.wallak.co.il/" target="_blank" style="text-decoration: none;">
            <h1 style="font-family: 'Arial', sans-serif; font-weight: 900; color: #000; font-size: 46px;">
                <span style="background-color: #000; color: #fff; padding: 0 12px; border-radius: 6px;">NEXT</span>DESIGN
            </h1>
        </a>
        <h3 style="color: #666; font-weight: 400; margin-top: 5px;">קטלוג חכם לסוכנים 🔎</h3>
    </div>
""", unsafe_allow_html=True)

# --- פונקציות עזר ---
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_min_price(details_list):
    prices = []
    for detail in details_list:
        d_up = detail.upper()
        if any(k in d_up for k in ['USD', 'PRICE', '$']):
            matches = re.findall(r'\d*\.\d+|\d+', detail)
            for match in matches:
                try:
                    val = float(match)
                    if val > 0: prices.append(val)
                except: pass
    return min(prices) if prices else None

def extract_moq(details_list):
    for detail in details_list:
        if 'MOQ' in detail.upper():
            nums = re.findall(r'\d+', detail.replace(',', ''))
            if nums: return int(nums[0])
    return None

def extract_delivery_days(details_list):
    for detail in details_list:
        d_up = detail.upper()
        if any(k in d_up for k in ['DELIVERY', 'DAYS', 'LEAD TIME']):
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
    if any(k in text_lower for k in ['stainless', '304', '316']): materials.append('Stainless Steel')
    if any(k in text_lower for k in ['plastic', 'pp', 'tritan']): materials.append('Plastic')
    for m in ['bamboo', 'glass', 'silicone', 'ceramic']:
        if m in text_lower: materials.append(m.capitalize())
    return list(set(materials))

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
        # תיקון: תמיכה בכונן משותף
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
    
    # תיקון: סריקת אקסלים בכונן משותף
    results = service.files().list(
        q=f"'{FOLDER_ID_EXCELS}' in parents", 
        fields="files(id, name)",
        supportsAllDrives=True, 
        includeItemsFromAllDrives=True
    ).execute()
    
    all_products = []
    
    for item in results.get('files', []):
        try:
            # תיקון: הורדת אקסל מכונן משותף
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
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', 'DESCRIPTION']):
                    details = []
                    item_key = ""
                    for offset in range(25):
                        curr_idx = idx + offset
                        if curr_idx >= len(df_file): skip_until = curr_idx; break
                        b_row = df_file.iloc[curr_idx].dropna().astype(str)
                        line = " ".join(b_row).strip()
                        if offset > 1 and any(k in line.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:']):
                            skip_until = curr_idx; break
                        if line and not any(x in line.upper() for x in ['WEB', 'HTTP', 'EXCHANGE RATE']):
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
                            'materials': extract_materials(full_text_str)
                        })
        except: continue
    
    # תיקון: סריקת תמונות בכונן משותף
    img_results = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents", 
        fields="files(id, name)",
        supportsAllDrives=True, 
        includeItemsFromAllDrives=True
    ).execute()
    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map

df, img_map = load_all_data()

# --- תפריט צד וחיפוש ---
with st.sidebar:
    st.header("⚙️ סינון חכם")
    price_min, price_max = st.slider("טווח מחיר ליח' (USD)", 0.0, 30.0, (0.0, 30.0), 0.1)
    max_moq = st.number_input("MOQ מקסימלי", 0, 100000, 50000)
    max_delivery = st.slider("זמן אספקה מקסימלי (ימים)", 5, 90, 90)
    available_materials = ["Stainless Steel", "Plastic", "Bamboo", "Glass", "Silicone", "Ceramic"]
    available_capacities = sorted([c for c in df['capacity'].unique() if c]) if not df.empty else []
    selected_materials = st.multiselect("חומר", available_materials)
    selected_capacities = st.multiselect("נפח", available_capacities)
    
    if st.session_state.selected_items:
        st.divider()
        st.header(f"🛒 נבחרו {len(st.session_state.selected_items)} מוצרים")
        # (כאן נשאר קוד יצירת המייל שלך כפי שהוא)
        if st.button("🗑️ נקה רשימה"):
            st.session_state.selected_items = {}; st.rerun()

search_input = st.text_input("", placeholder="🔍 הקלד שם מוצר לחיפוש (למשל: Bottle)...")

if not df.empty and search_input:
    service = get_gdrive_service()
    term = normalize_text(search_input)
    term_trans = normalize_text(transform_he_to_en(search_input))
    results = df[df['normalized_text'].str.contains(term, na=False) | df['normalized_text'].str.contains(term_trans, na=False)].copy()
    
    if not results.empty:
        # סינון לפי בחירות המשתמש
        if price_min > 0.0 or price_max < 30.0: results = results[results['min_price'].apply(lambda x: x is not None and price_min <= x <= price_max)]
        if max_moq < 50000: results = results[results['moq'].apply(lambda x: x is None or x <= max_moq)]
        if max_delivery < 90: results = results[results['delivery_days'].apply(lambda x: x is not None and x <= max_delivery)]
        if selected_materials: results = results[results['materials'].apply(lambda x: any(m in x for m in selected_materials))]
        if selected_capacities: results = results[results['capacity'].isin(selected_capacities)]

        results = results.drop_duplicates(subset=['item_key', 'file_source'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(results.iterrows()):
            unique_item_id = f"{row['base_filename']}_{row['row_index']}"
            with cols[i % 4]:
                with st.container(border=True):
                    if st.checkbox("➕ בחר", value=(unique_item_id in st.session_state.selected_items), key=f"chk_{unique_item_id}"):
                        st.session_state.selected_items[unique_item_id] = row
                    else: st.session_state.selected_items.pop(unique_item_id, None)
                    
                    # חיפוש תמונה מתאימה
                    img_id = None
                    base_name_clean = normalize_text(row['base_filename'])
                    valid_images = {name: i_id for name, i_id in img_map.items() if base_name_clean in normalize_text(name)}
                    if valid_images:
                        row_target = f"row_{row['row_index']}"
                        for name, i_id in valid_images.items():
                            if row_target in normalize_text(name): img_id = i_id; break
                        if not img_id: img_id = list(valid_images.values())[i % len(valid_images)]
                    
                    img_html = '<div style="color:#aaa; font-size:12px;">📷 אין תמונה</div>'
                    if img_id:
                        img_b64 = get_image_base64(service, img_id)
                        if img_b64:
                            img_html = f'<img src="data:image/jpeg;base64,{img_b64}" style="width:100%; height:200px; object-fit:contain;">'

                    # תגיות
                    tags_html = f"<div style='margin-bottom:5px;'>"
                    if row['moq']: tags_html += f"<span style='background:#f1c40f; padding:2px 5px; border-radius:4px; font-size:10px;'>MOQ: {row['moq']}</span> "
                    if row['capacity']: tags_html += f"<span style='background:#eee; padding:2px 5px; border-radius:4px; font-size:10px;'>{row['capacity']}</span>"
                    tags_html += "</div>"

                    # בניית כרטיס המוצר
                    st.markdown(f"""
                        <div style="height: 580px; display: flex; flex-direction: column;">
                            <div style="text-align:center;">{img_html}</div>
                            {tags_html}
                            <div style="flex-grow:1; overflow-y:auto; font-size:13px; text-align:left;">
                                {''.join([f"<div>• {d}</div>" for d in row['display_list'] if not contains_chinese(d)])}
                            </div>
                            <div style="border-top:1px solid #eee; padding-top:5px; font-size:11px; color:#aaa;">📂 {row['file_source']}</div>
                        </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("לא נמצאו תוצאות.")
