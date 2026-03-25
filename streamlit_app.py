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

# ייבוא המפתח מקובץ constants.py
try:
    from constants import RAW_KEY
except ImportError:
    st.error("שגיאה: קובץ constants.py לא נמצא. וודא שהוא קיים בתיקייה עם המשתנה RAW_KEY")
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
    
    .stTextInput > div > div > input {
        border-radius: 30px !important; border: 2px solid #eaeaea !important;
        padding: 15px 20px !important;
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

# --- פונקציות לוגיקה ---
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', str(text)))

def extract_min_price(details_list):
    prices = []
    for detail in details_list:
        d_up = str(detail).upper()
        if any(x in d_up for x in ['USD', 'PRICE', '$']):
            matches = re.findall(r'\d*\.\d+|\d+', str(detail))
            for m in matches:
                try:
                    v = float(m)
                    if 0.1 < v < 1000: prices.append(v)
                except: pass
    return min(prices) if prices else None

def extract_moq(details_list):
    for d in details_list:
        if 'MOQ' in str(d).upper():
            nums = re.findall(r'\d+', str(d).replace(',', ''))
            if nums: return int(nums[0])
    return None

def extract_delivery_days(details_list):
    for d in details_list:
        d_up = str(d).upper()
        if any(x in d_up for x in ['DELIVERY', 'DAYS', 'LEAD TIME']):
            if 'SAMPLE' not in d_up:
                nums = re.findall(r'\d+', str(d))
                if nums: return max([int(n) for n in nums])
    return None

def normalize_text(text):
    return re.sub(r'[^a-zA-Z0-9\u0590-\u05FF]', '', str(text)).lower()

def transform_he_to_en(text):
    he_en_map = {'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g', 'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n', 'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u', 'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y'}
    return "".join([he_en_map.get(char, char) for char in text.lower()])

# --- חיבור לגוגל ---
def get_gdrive_service():
    try:
        info = json.loads(base64.b64decode(re.sub(r'[^A-Za-z0-9+/=]', '', RAW_KEY)).decode('utf-8'))
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"שגיאת חיבור: {e}")
        return None

@st.cache_data(ttl=3600)
def get_image_b64(_service, f_id):
    try:
        request = _service.files().get_media(fileId=f_id)
        fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except: return None

@st.cache_data(ttl=600)
def load_all_data():
    service = get_gdrive_service()
    if not service: return pd.DataFrame(), {}
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
                row_str = " ".join(df_ex.iloc[i].dropna().astype(str))
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'DESCRIPTION']):
                    details = [str(v) for v in df_ex.iloc[i:i+20, :].values.flatten() if pd.notna(v) and str(v).strip()]
                    txt = " ".join(details)
                    all_p.append({
                        'item_key': details[0], 'display_list': details[:15],
                        'normalized_text': normalize_text(txt),
                        'base_filename': f['name'].rsplit('.', 1)[0],
                        'min_price': extract_min_price(details),
                        'moq': extract_moq(details),
                        'delivery': extract_delivery_days(details)
                    })
        except: continue
    imgs = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents").execute().get('files', [])
    img_map = {img['name'].rsplit('.', 1)[0]: img['id'] for img in imgs}
    return pd.DataFrame(all_p), img_map

df, img_map = load_all_data()

# --- ממשק ---
with st.sidebar:
    st.header("⚙️ סינון חכם")
    p_min, p_max = st.slider("מחיר (USD)", 0.0, 30.0, (0.0, 30.0), 0.1)
    max_moq = st.number_input("MOQ מקסימלי", value=10000)
    max_del = st.slider("זמן אספקה (ימים)", 5, 90, 90)
    
    st.divider()
    if st.session_state.selected_items:
        st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")
        email_body = "להלן המוצרים שבחרתי:\n\n"
        for _, itm in st.session_state.selected_items.items():
            email_body += f"- {itm['item_key']}\n"
        st.markdown(f'<a href="mailto:?subject=Next Design&body={urllib.parse.quote(email_body)}" class="email-btn">✉️ שלח מייל</a>', unsafe_allow_html=True)
        if st.button("🗑️ נקה"): st.session_state.selected_items = {}; st.rerun()

st.markdown('<h1 style="text-align:center;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search = st.text_input("", placeholder="🔍 חפש מוצר...")

if not df.empty and search:
    service = get_gdrive_service()
    term = normalize_text(search)
    term_en = normalize_text(transform_he_to_en(search))
    res = df[df['normalized_text'].str.contains(term) | df['normalized_text'].str.contains(term_en)].copy()
    
    # הפעלת פילטרים
    res = res[(res['min_price'].fillna(0) <= p_max) & (res['moq'].fillna(0) <= max_moq)]

    if not res.empty:
        cols = st.columns(4)
        for i, (_, row) in enumerate(res.iterrows()):
            with cols[i % 4]:
                with st.container(border=True):
                    st.checkbox("בחר", key=f"sel_{i}", value=row['item_key'] in st.session_state.selected_items)
                    
                    f_id = img_map.get(row['base_filename'])
                    if f_id:
                        b64 = get_image_b64(service, f_id)
                        if b64: st.markdown(f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; height:200px; object-fit:contain; border-radius:8px; margin-bottom:10px;">', unsafe_allow_html=True)
                    
                    st.write(f"**{row['item_key']}**")
                    if row['moq']: st.markdown(f"<span style='background:#f1c40f; padding:2px 5px; border-radius:4px; font-size:11px;'>📦 MOQ: {row['moq']}</span>", unsafe_allow_html=True)
                    
                    for d in row['display_list']:
                        d_up = str(d).upper()
                        if not contains_chinese(d) and not any(x in d_up for x in ['ITEM NO', 'FOB COST', 'WEB', 'HTTP', 'VALIDITY']):
                            if 'USD' in d_up: st.write(f"💰 **{d}**")
                            else: st.write(f"<small>• {d}</small>", unsafe_allow_html=True)
