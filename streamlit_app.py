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

# ייבוא המפתח
try:
    from constants import RAW_KEY
except ImportError:
    st.error("קובץ constants.py חסר!")
    st.stop()

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

# --- הגדרות קבועות ---
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}

# --- עיצוב CSS (ביטול כל חסימה אפשרית) ---
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

    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important;
        background-color: white; padding: 15px !important;
        min-height: auto !important;
        display: block !important;
        overflow: visible !important;
    }
    
    .img-box {
        width: 100%;
        text-align: center;
        margin-bottom: 15px;
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

def normalize_text(text):
    if not isinstance(text, str): text = str(text)
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '', text).lower()

def transform_he_to_en(text):
    he_en_map = {'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g', 'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n', 'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u', 'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y'}
    return "".join([he_en_map.get(char, char) for char in text.lower()])

def get_gdrive_service():
    try:
        encoded = re.sub(r'[^A-Za-z0-9+/=]', '', RAW_KEY)
        info = json.loads(base64.b64decode(encoded).decode('utf-8'))
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"שגיאה במפתח: {e}")
        return None

@st.cache_data(ttl=3600)
def fetch_image_b64(_service, f_id):
    try:
        request = _service.files().get_media(fileId=f_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except:
        return None

@st.cache_data(ttl=600)
def load_data():
    service = get_gdrive_service()
    if not service: return pd.DataFrame(), {}
    
    # טעינת אקסלים
    files = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    data = []
    for f in files.get('files', []):
        try:
            request = service.files().get_media(fileId=f['id'])
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df_ex = pd.read_excel(fh, header=None, engine='xlrd' if f['name'].endswith('.xls') else None)
            for i in range(len(df_ex)):
                row_str = " ".join(df_ex.iloc[i].dropna().astype(str))
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', 'DESCRIPTION']):
                    details = []
                    item_key = ""
                    for offset in range(25):
                        curr = i + offset
                        if curr >= len(df_ex): break
                        line = " ".join(df_ex.iloc[curr].dropna().astype(str)).strip()
                        if line:
                            details.append(line)
                            if 'ITEM' in line.upper() and not item_key: item_key = line
                    if details:
                        full_txt = " ".join(details)
                        data.append({
                            'item_key': item_key if item_key else details[0],
                            'display_list': details,
                            'normalized_text': normalize_text(full_txt),
                            'base_filename': f['name'].rsplit('.', 1)[0],
                            'row_idx': i
                        })
        except: continue
    
    # מיפוי תמונות
    imgs = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(id, name)").execute()
    img_map = {img['name'].rsplit('.', 1)[0]: img['id'] for img in imgs.get('files', [])}
    return pd.DataFrame(data), img_map

df, img_map = load_data()

# --- ממשק ---
with st.sidebar:
    st.header("🛒 סל מוצרים")
    if st.session_state.selected_items:
        st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")
        if st.button("🗑️ נקה סל"):
            st.session_state.selected_items = {}
            st.rerun()

st.markdown('<h1 style="text-align:center;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search = st.text_input("", placeholder="🔍 חפש מוצר...")

if not df.empty and search:
    service = get_gdrive_service()
    term = normalize_text(search)
    term_en = normalize_text(transform_he_to_en(search))
    res = df[df['normalized_text'].str.contains(term, na=False) | df['normalized_text'].str.contains(term_en, na=False)].copy()
    
    if not res.empty:
        res = res.drop_duplicates(subset=['item_key'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(res.iterrows()):
            u_id = f"{row['base_filename']}_{row['row_idx']}"
            with cols[i % 4]:
                with st.container(border=True):
                    is_sel = u_id in st.session_state.selected_items
                    if st.checkbox("➕ בחר", value=is_sel, key=f"c_{u_id}"):
                        st.session_state.selected_items[u_id] = row
                    
                    # הצגת תמונה Base64 ישירה
                    img_id = img_map.get(row['base_filename'])
                    if img_id:
                        b64_data = fetch_image_b64(service, img_id)
                        if b64_data:
                            st.markdown(f'''
                                <div class="img-box">
                                    <img src="data:image/jpeg;base64,{b64_data}" 
                                    style="max-width:100%; height:200px; object-fit:contain; border-radius:8px;">
                                </div>
                            ''', unsafe_allow_html=True)
                    
                    st.write(f"**{row['item_key']}**")
                    for d in row['display_list']:
                        d_up = d.upper()
                        if not contains_chinese(d) and not any(x in d_up for x in ['ITEM NO', 'ITEM:', 'FOB COST', 'FOB PORT', 'WEB', 'HTTP', 'VALIDITY']):
                            if 'USD' in d_up: st.write(f"💰 **{d}**")
                            else: st.write(f"<small>• {d}</small>", unsafe_allow_html=True)
