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

# ייבוא המפתח מקובץ חיצוני
try:
    from constants import RAW_KEY
except ImportError:
    st.error("קובץ constants.py חסר! צור אותו עם המפתח שלך.")
    st.stop()

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

# --- הגדרות קבועות ---
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}

# --- עיצוב CSS המקורי שלך ---
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
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important;
        background-color: white; padding: 15px !important; position: relative;
    }
    .email-btn {
        display: block; width: 100%; text-align: center; background-color: #27ae60;
        color: white !important; padding: 10px; border-radius: 8px; text-decoration: none;
        font-weight: bold; margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- פונקציות ---
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def transform_he_to_en(text):
    he_en_map = {'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g', 'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n', 'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u', 'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y', 'ז': 'z'}
    return "".join([he_en_map.get(char, char) for char in text.lower()])

def normalize_text(text):
    if not isinstance(text, str): text = str(text)
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '', text).lower()

def get_gdrive_service():
    try:
        decoded_key = base64.b64decode(re.sub(r'[^A-Za-z0-9+/=]', '', RAW_KEY)).decode('utf-8')
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
    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    all_products = []
    for item in results.get('files', []):
        try:
            request = service.files().get_media(fileId=item['id'])
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df = pd.read_excel(fh, header=None)
            for idx in range(len(df)):
                row_str = " ".join(df.iloc[idx].dropna().astype(str))
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', '*ITEM', 'DESCRIPTION']):
                    details = []
                    for offset in range(25):
                        curr_idx = idx + offset
                        if curr_idx >= len(df): break
                        line = " ".join(df.iloc[curr_idx].dropna().astype(str)).strip()
                        if offset > 1 and any(k in line.upper() for k in ['ITEM NO', 'ITEM REF']): break
                        if line: details.append(line)
                    if details:
                        full_txt = " ".join(details)
                        all_products.append({
                            'item_key': details[0], 'display_list': details,
                            'normalized_text': normalize_text(full_txt),
                            'file_source': item['name'],
                            'base_filename': item['name'].rsplit('.', 1)[0],
                            'row_index': idx
                        })
        except: continue
    img_results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(id, name)").execute()
    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map

df, img_map = load_all_data()

# --- חיפוש ותצוגה ---
st.markdown('<h1 style="text-align:center;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search_input = st.text_input("", placeholder="🔍 חפש מוצר...")

if not df.empty and search_input:
    service = get_gdrive_service()
    term = normalize_text(search_input)
    term_trans = normalize_text(transform_he_to_en(search_input))
    results = df[df['normalized_text'].str.contains(term, na=False) | df['normalized_text'].str.contains(term_trans, na=False)].copy()
    
    if not results.empty:
        results = results.drop_duplicates(subset=['item_key', 'file_source'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(results.iterrows()):
            unique_id = f"{row['base_filename']}_{row['row_index']}"
            with cols[i % 4]:
                with st.container(border=True):
                    st.checkbox("➕ בחר", key=f"c_{unique_id}")
                    
                    # --- מנגנון התמונות המדויק מהקוד שלך ---
                    img_id = None
                    base_name_clean = normalize_text(row['base_filename'])
                    valid_images = {name: i_id for name, i_id in img_map.items() if base_name_clean in normalize_text(name)}
                    if valid_images:
                        row_target = f"row_{row['row_index']}"
                        for name, i_id in valid_images.items():
                            if row_target in normalize_text(name): img_id = i_id; break
                        if not img_id: img_id = list(valid_images.values())[0]
                    
                    if img_id:
                        b64 = get_image_base64(service, img_id)
                        if b64: st.markdown(f'<div style="height:200px; display:flex; align-items:center; justify-content:center;"><img src="data:image/jpeg;base64,{b64}" style="max-height:100%; max-width:100%; object-fit:contain; border-radius:8px;"></div>', unsafe_allow_html=True)
                    
                    st.write(f"**{row['item_key']}**")
                    for detail in row['display_list']:
                        d_up = detail.upper()
                        if not contains_chinese(detail) and not any(x in d_up for x in ['WEB', 'HTTP', 'HTTPS', 'VALIDITY', 'FOB PORT']):
                            if 'USD' in d_up: st.write(f"💰 **{detail}**")
                            else: st.write(f"<small>• {detail}</small>", unsafe_allow_html=True)
