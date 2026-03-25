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

# ניסיון ייבוא המפתח מקובץ constants.py
try:
    from constants import RAW_KEY
except ImportError:
    st.error("קובץ constants.py חסר! צור קובץ בשם constants.py עם השורה: RAW_KEY = '...' ")
    st.stop()

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

# --- הגדרות קבועות ---
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}

# --- עיצוב CSS מתוקן ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px; }
    
    .stTextInput > div > div > input {
        border-radius: 30px !important; border: 2px solid #eaeaea !important;
        padding: 10px 20px !important;
    }

    /* תיקון קוביות המוצר - גובה גמיש ותצוגה יציבה לתמונות */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important;
        background-color: white; padding: 15px !important; 
        position: relative;
        min-height: auto !important;
        max-height: none !important;
        overflow: visible !important;
        display: block !important;
    }
    
    .email-btn {
        display: block; width: 100%; text-align: center; background-color: #27ae60;
        color: white !important; padding: 10px; border-radius: 8px; text-decoration: none;
        font-weight: bold; margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- פונקציות לוגיקה ---
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
        if 'MOQ' in detail.upper():
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
    if 'stainless' in text_lower or '304' in text_lower: materials.append('Stainless Steel')
    if 'plastic' in text_lower or 'pp' in text_lower: materials.append('Plastic')
    if 'glass' in text_lower: materials.append('Glass')
    if 'bamboo' in text_lower: materials.append('Bamboo')
    return list(set(materials))

def transform_he_to_en(text):
    he_en_map = {'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g', 'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n', 'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u', 'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y'}
    return "".join([he_en_map.get(char, char) for char in text.lower()])

def normalize_text(text):
    if not isinstance(text, str): text = str(text)
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '', text).lower()

def get_gdrive_service():
    try:
        encoded_key = re.sub(r'[^A-Za-z0-9+/=]', '', RAW_KEY)
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
        request = _service.files().get_media(fileId=file_id)
        fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except: return None

@st.cache_data(ttl=600)
def load_all_data():
    service = get_gdrive_service()
    if not service: return pd.DataFrame(), {}
    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    all_products = []
    for item in results.get('files', []):
        try:
            request = service.files().get_media(fileId=item['id'])
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df_excel = pd.read_excel(fh, header=None, engine='xlrd' if item['name'].endswith('.xls') else None)
            for idx in range(len(df_excel)):
                row_str = " ".join(df_excel.iloc[idx].dropna().astype(str))
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', 'DESCRIPTION']):
                    details = []
                    item_key = ""
                    for offset in range(25):
                        curr_idx = idx + offset
                        if curr_idx >= len(df_excel): break
                        line = " ".join(df_excel.iloc[curr_idx].dropna().astype(str)).strip()
                        if line:
                            details.append(line)
                            if 'ITEM' in line.upper() and not item_key: item_key = line
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
    img_results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(id, name)").execute()
    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map

df, img_map = load_all_data()

# --- ממשק ---
with st.sidebar:
    st.header("⚙️ סינון חכם")
    price_min, price_max = st.slider("טווח מחיר (USD)", 0.0, 30.0, (0.0, 30.0), 0.1)
    max_moq = st.number_input("MOQ מקסימלי (0 = הכל)", value=0, min_value=0)
    max_delivery = st.slider("זמן אספקה מקסימלי (ימים)", 5, 90, 90, 5)
    
    available_materials = ["Stainless Steel", "Plastic", "Bamboo", "Glass"]
    selected_materials = st.multiselect("חומר", available_materials)
    
    available_capacities = sorted([c for c in df['capacity'].unique() if c]) if not df.empty else []
    selected_capacities = st.multiselect("נפח (Capacity)", available_capacities)
    
    st.divider()
    st.header("🛒 סל מוצרים")
    if st.session_state.selected_items:
        st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")
        if st.button("🗑️ נקה סל"):
            st.session_state.selected_items = {}
            st.rerun()

st.markdown('<h1 style="text-align:center;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search_input = st.text_input("", placeholder="🔍 (Bottle למשל) חפש מוצר...")

if not df.empty and search_input:
    service = get_gdrive_service()
    term = normalize_text(search_input)
    term_trans = normalize_text(transform_he_to_en(search_input))
    results = df[df['normalized_text'].str.contains(term, na=False) | df['normalized_text'].str.contains(term_trans, na=False)].copy()
    
    if not results.empty:
        if price_min > 0.0 or price_max < 30.0:
            results = results[results['min_price'].apply(lambda x: x is not None and price_min <= x <= price_max)]
        if max_moq > 0:
            results = results[results['moq'].apply(lambda x: x is not None and x <= max_moq)]
        if max_delivery < 90:
            results = results[results['delivery_days'].apply(lambda x: x is not None and x <= max_delivery)]
        if selected_materials:
            results = results[results['materials'].apply(lambda x: any(m in x for m in selected_materials))]
        if selected_capacities:
            results = results[results['capacity'].isin(selected_capacities)]

    if not results.empty:
        results = results.drop_duplicates(subset=['item_key'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(results.iterrows()):
            unique_id = f"{row['base_filename']}_{row['row_index']}"
            with cols[i % 4]:
                with st.container(border=True):
                    is_sel = unique_id in st.session_state.selected_items
                    if st.checkbox("➕ בחר", value=is_sel, key=f"c_{unique_id}"):
                        st.session_state.selected_items[unique_id] = row
                    elif unique_id in st.session_state.selected_items:
                        del st.session_state.selected_items[unique_id]
                    
                    img_id = img_map.get(row['base_filename'] + ".jpg") or img_map.get(row['base_filename'] + ".png")
                    if img_id:
                        b64 = get_image_base64(service, img_id)
                        if b64: st.markdown(f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; height:220px; object-fit:contain; border-radius:8px; margin-bottom:10px;">', unsafe_allow_html=True)
                    
                    st.write(f"**{row['item_key']}**")
                    tags = ""
                    if row['moq']: tags += f"<span style='background:#f1c40f; padding:2px 5px; border-radius:4px; font-size:11px;'>📦 MOQ: {row['moq']}</span> "
                    if row['capacity']: tags += f"<span style='background:#eee; padding:2px 5px; border-radius:4px; font-size:11px;'>💧 {row['capacity']}</span>"
                    st.markdown(tags, unsafe_allow_html=True)
                    
                    for detail in row['display_list']:
                        d_up = detail.upper()
                        # סינון כפילויות של מידע שכבר מופיע למעלה או מידע לא רלוונטי
                        if not contains_chinese(detail) and not any(x in d_up for x in ['ITEM NO', 'ITEM:', 'MOQ:', 'FOB COST', 'FOB PORT', 'WEB', 'HTTP', 'VALIDITY']):
                            if 'USD' in d_up: st.write(f"💰 **{detail}**")
                            elif 'DELIVERY' in d_up or 'DAYS' in d_up: st.write(f"🚚 <small>{detail}</small>", unsafe_allow_html=True)
                            else: st.write(f"<small>• {detail}</small>", unsafe_allow_html=True)
