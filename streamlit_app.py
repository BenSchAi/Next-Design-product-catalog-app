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

# --- עיצוב CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px; }
    .stTextInput > div > div > input { border-radius: 30px !important; border: 2px solid #eaeaea !important; padding: 10px 20px !important; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        background-color: white; padding: 15px !important; min-height: auto !important; display: block !important;
    }
    .email-btn { display: block; width: 100%; text-align: center; background-color: #27ae60; color: white !important; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- פונקציות לוגיקה ---
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_min_price(details_list):
    prices = []
    for detail in details_list:
        if any(x in detail.upper() for x in ['USD', 'PRICE', '$']):
            matches = re.findall(r'\d*\.\d+|\d+', detail)
            for m in matches:
                try:
                    val = float(m)
                    if 0.1 < val < 1000: prices.append(val)
                except: pass
    return min(prices) if prices else None

def extract_moq(details_list):
    for detail in details_list:
        if 'MOQ' in detail.upper():
            nums = re.findall(r'\d+', detail.replace(',', ''))
            if nums: return int(nums[0])
    return None

def normalize_text(text):
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '', str(text)).lower()

def transform_he_to_en(text):
    he_en_map = {'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g', 'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n', 'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u', 'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y'}
    return "".join([he_en_map.get(char, char) for char in text.lower()])

def get_service():
    info = json.loads(base64.b64decode(re.sub(r'[^A-Za-z0-9+/=]', '', RAW_KEY)).decode('utf-8'))
    return build('drive', 'v3', credentials=service_account.Credentials.from_service_account_info(info))

@st.cache_data(ttl=3600)
def get_img_b64(f_id):
    try:
        service = get_service()
        request = service.files().get_media(fileId=f_id)
        fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except: return None

@st.cache_data(ttl=600)
def load_all():
    service = get_service()
    files = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents").execute().get('files', [])
    all_p = []
    for f in files:
        try:
            request = service.files().get_media(fileId=f['id'])
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df_ex = pd.read_excel(fh, header=None)
            for i in range(len(df_ex)):
                row_s = " ".join(df_ex.iloc[i].dropna().astype(str))
                if any(k in row_s.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', 'DESCRIPTION']):
                    details = [str(line) for line in df_ex.iloc[i:i+20, :].values.flatten() if pd.notna(line) and str(line).strip()]
                    item_key = details[0]
                    all_p.append({
                        'item_key': item_key, 'display_list': details[:12],
                        'normalized_text': normalize_text(" ".join(details)),
                        'base_filename': f['name'].rsplit('.', 1)[0],
                        'min_price': extract_min_price(details),
                        'moq': extract_moq(details)
                    })
        except: continue
    imgs = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents").execute().get('files', [])
    img_map = {img['name'].rsplit('.', 1)[0]: img['id'] for img in imgs}
    return pd.DataFrame(all_p), img_map

df, img_map = load_all()

# --- ממשק ---
with st.sidebar:
    st.header("⚙️ סינון")
    p_min, p_max = st.slider("מחיר (USD)", 0.0, 30.0, (0.0, 30.0), 0.1)
    m_moq = st.number_input("MOQ מקסימלי", value=0)
    if st.session_state.selected_items:
        st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")
        if st.button("🗑️ נקה"):
            st.session_state.selected_items = {}
            st.rerun()

st.markdown('<h1 style="text-align:center;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search_in = st.text_input("", placeholder="🔍 חפש...")

if not df.empty and search_in:
    term = normalize_text(search_in)
    term_en = normalize_text(transform_he_to_en(search_in))
    res = df[df['normalized_text'].str.contains(term) | df['normalized_text'].str.contains(term_en)].copy()
    
    if m_moq > 0: res = res[res['moq'].fillna(0) <= m_moq]
    res = res[res['min_price'].between(p_min, p_max) | res['min_price'].isna()]

    if not res.empty:
        res = res.drop_duplicates(subset=['item_key'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(res.iterrows()):
            with cols[i % 4]:
                with st.container(border=True):
                    st.checkbox("➕ בחר", key=f"c_{row['item_key']}_{i}")
                    
                    # הצגת תמונה
                    f_id = img_map.get(row['base_filename'])
                    if f_id:
                        b64 = get_img_b64(f_id)
                        if b64: st.markdown(f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; height:200px; object-fit:contain; border-radius:8px;">', unsafe_allow_html=True)
                    
                    st.write(f"**{row['item_key']}**")
                    if row['moq']: st.markdown(f"<span style='background:#f1c40f; padding:2px 5px; border-radius:4px; font-size:11px;'>📦 MOQ: {row['moq']}</span>", unsafe_allow_html=True)
                    
                    for d in row['display_list']:
                        d_u = str(d).upper()
                        if not contains_chinese(str(d)) and not any(x in d_u for x in ['ITEM NO', 'FOB COST', 'WEB', 'HTTP', 'VALIDITY']):
                            if 'USD' in d_u: st.write(f"💰 **{d}**")
                            else: st.write(f"<small>• {d}</small>", unsafe_allow_html=True)
