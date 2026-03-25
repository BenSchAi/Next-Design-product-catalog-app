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

# ייבוא המפתח מהקובץ הנפרד שיצרת
try:
    from constants import RAW_KEY
except ImportError:
    st.error("שגיאה: קובץ constants.py לא נמצא. אנא צור אותו עם המפתח שלך.")
    st.stop()

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

# --- הגדרות קבועות ---
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}

# --- עיצוב CSS מתוקן (גובה גמיש לתמונות) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px; }
    
    .stTextInput > div > div > input {
        border-radius: 30px !important; border: 2px solid #eaeaea !important;
        padding: 15px 20px !important; font-size: 16px !important;
    }

    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important;
        background-color: white; padding: 15px !important; 
        min-height: auto !important;
        display: block !important;
    }
    
    .email-btn {
        display: block; width: 100%; text-align: center; background-color: #27ae60;
        color: white !important; padding: 10px; border-radius: 8px; text-decoration: none;
        font-weight: bold; margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- פונקציות עזר ---
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

def normalize_text(text):
    if not isinstance(text, str): text = str(text)
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '', text).lower()

# --- חיבור לגוגל ---
def get_gdrive_service():
    try:
        # ניקוי המפתח שהגיע מהקובץ החיצוני
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
                    for offset in range(15):
                        curr_idx = idx + offset
                        if curr_idx >= len(df_excel): break
                        line = " ".join(df_excel.iloc[curr_idx].dropna().astype(str)).strip()
                        if line:
                            details.append(line)
                            if 'ITEM' in line.upper() and not item_key: item_key = line
                    if details:
                        all_products.append({
                            'item_key': item_key if item_key else details[0],
                            'display_list': details,
                            'normalized_text': normalize_text(" ".join(details)),
                            'base_filename': item['name'].rsplit('.', 1)[0],
                            'row_index': idx,
                            'min_price': extract_min_price(details),
                            'moq': extract_moq(details)
                        })
        except: continue
    img_results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(id, name)").execute()
    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map

df, img_map = load_all_data()

# --- ממשק ---
with st.sidebar:
    st.header("⚙️ סינון חכם")
    max_moq = st.number_input("MOQ מקסימלי (0 = הכל)", value=0, min_value=0)
    st.divider()
    if st.session_state.selected_items:
        st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")
        if st.button("🗑️ נקה סל"):
            st.session_state.selected_items = {}
            st.rerun()

st.markdown('<h1 style="text-align:center;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search_input = st.text_input("", placeholder="🔍 חפש מוצר...")

if not df.empty and search_input:
    service = get_gdrive_service()
    term = normalize_text(search_input)
    results = df[df['normalized_text'].str.contains(term, na=False)].copy()
    
    if max_moq > 0:
        results = results[results['moq'].apply(lambda x: x is not None and x <= max_moq)]

    if not results.empty:
        results = results.drop_duplicates(subset=['item_key'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(results.iterrows()):
            unique_id = f"{row['base_filename']}_{row['row_index']}"
            with cols[i % 4]:
                with st.container(border=True):
                    if st.checkbox("➕ בחר", key=f"c_{unique_id}"):
                        st.session_state.selected_items[unique_id] = row
                    
                    img_id = img_map.get(row['base_filename'] + ".jpg") or img_map.get(row['base_filename'] + ".png")
                    if img_id:
                        b64 = get_image_base64(service, img_id)
                        if b64: st.markdown(f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; height:200px; object-fit:contain; border-radius:8px; margin-bottom:10px;">', unsafe_allow_html=True)
                    
                    st.write(f"**{row['item_key']}**")
                    if row['moq']: st.markdown(f"<span style='background:#f1c40f; padding:2px 5px; border-radius:4px; font-size:11px;'>📦 MOQ: {row['moq']}</span>", unsafe_allow_html=True)
                    
                    for detail in row['display_list']:
                        d_up = detail.upper()
                        if not contains_chinese(detail) and not any(x in d_up for x in ['ITEM NO', 'MOQ:', 'FOB COST', 'FOB PORT', 'WEB', 'HTTP', 'VALIDITY']):
                            if 'USD' in d_up: st.write(f"💰 **{detail}**")
                            else: st.write(f"<small>• {detail}</small>", unsafe_allow_html=True)
