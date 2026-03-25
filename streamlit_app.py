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
    st.error("קובץ constants.py חסר!")
    st.stop()

st.set_page_config(page_title="Next Design - קטלוג חכם", layout="wide", initial_sidebar_state="expanded")

# --- הגדרות קבועות ---
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = {}

# --- עיצוב CSS לאחידות וצבעוניות ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    .block-container { padding-top: 2rem; max-width: 1300px; }
    
    /* עיצוב תיבת החיפוש */
    .stTextInput > div > div > input {
        border-radius: 30px !important; border: 2px solid #eaeaea !important;
        padding: 12px 20px !important; font-size: 16px !important;
    }

    /* קוביית מוצר אחידה */
    .product-card {
        background-color: white;
        border: 1px solid #f0f0f0;
        border-radius: 15px;
        padding: 15px;
        height: 650px;
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: transform 0.2s;
        margin-bottom: 20px;
    }
    .product-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.05); }

    /* אזור התמונה */
    .img-container {
        height: 220px;
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 10px;
        background: #fff;
    }
    .img-container img { max-height: 100%; max-width: 100%; object-fit: contain; }

    /* אזור הטקסט עם גלילה פנימית אם צריך */
    .details-container {
        flex-grow: 1;
        overflow-y: auto;
        font-size: 13px;
        line-height: 1.4;
        color: #444;
        margin-top: 10px;
        padding-right: 5px;
    }
    
    .price-line { color: #27ae60; font-weight: 800; font-size: 15px; margin-top: 10px; border-top: 1px solid #eee; padding-top: 10px; }
    .moq-tag { background: #f1c40f; color: #000; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
    .cap-tag { background: #e1f5fe; color: #01579b; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 5px; }

    .email-btn {
        display: block; width: 100%; text-align: center; background-color: #27ae60;
        color: white !important; padding: 10px; border-radius: 8px; text-decoration: none;
        font-weight: bold; margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- פונקציות עזר ---
def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', str(text)))

def normalize_text(text):
    return re.sub(r'[^a-zA-Z0-9]', '', str(text)).lower()

def transform_he_to_en(text):
    he_en_map = {'ש': 'a', 'נ': 'b', 'ב': 'c', 'ג': 'd', 'ק': 'e', 'כ': 'f', 'ע': 'g', 'י': 'h', 'ן': 'i', 'ח': 'j', 'ל': 'k', 'ך': 'l', 'צ': 'm', 'מ': 'n', 'ם': 'o', 'פ': 'p', '/': 'q', 'ר': 'r', 'ד': 's', 'א': 't', 'ו': 'u', 'ה': 'v', 'ס': 'w', 'ז': 'x', 'ט': 'y'}
    return "".join([he_en_map.get(char, char) for char in text.lower()])

def get_service():
    info = json.loads(base64.b64decode(re.sub(r'[^A-Za-z0-9+/=]', '', RAW_KEY)).decode('utf-8'))
    return build('drive', 'v3', credentials=service_account.Credentials.from_service_account_info(info))

@st.cache_data(ttl=3600)
def get_img_b64(_service, f_id):
    try:
        request = _service.files().get_media(fileId=f_id)
        fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except: return None

@st.cache_data(ttl=600)
def load_all_data():
    service = get_service()
    if not service: return pd.DataFrame(), {}
    
    excels = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents").execute().get('files', [])
    all_p = []
    for f in excels:
        try:
            request = service.files().get_media(fileId=f['id'])
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df_ex = pd.read_excel(fh, header=None)
            for idx in range(len(df_ex)):
                row_str = " ".join(df_ex.iloc[idx].dropna().astype(str))
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'DESCRIPTION']):
                    details = []
                    item_no = ""
                    for offset in range(20):
                        curr = idx + offset
                        if curr >= len(df_ex): break
                        line = " ".join(df_ex.iloc[curr].dropna().astype(str)).strip()
                        if offset > 0 and any(k in line.upper() for k in ['ITEM NO', 'ITEM REF']): break
                        if line:
                            details.append(line)
                            if 'ITEM' in line.upper() and not item_no: item_no = line
                    
                    full_txt = " ".join(details)
                    # חילוץ מידע בסיסי לסינון
                    moq_match = re.search(r'MOQ:\s*(\d+)', full_txt.upper().replace(',', ''))
                    price_match = re.search(r'USD\s*(\d+\.\d+|\d+)', full_txt.upper())
                    cap_match = re.search(r'(\d+)\s*(ML|OZ)', full_txt.upper())

                    all_p.append({
                        'item_no': item_no if item_no else details[0],
                        'display_list': details,
                        'normalized_text': normalize_text(full_txt),
                        'base_filename': f['name'].rsplit('.', 1)[0],
                        'row_idx': idx,
                        'moq': int(moq_match.group(1)) if moq_match else None,
                        'price': float(price_match.group(1)) if price_match else None,
                        'capacity': cap_match.group(0) if cap_match else ""
                    })
        except: continue
        
    imgs = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents").execute().get('files', [])
    img_map = {img['name']: img['id'] for img in imgs}
    return pd.DataFrame(all_p), img_map

df, img_map = load_all_data()

# --- ממשק חיפוש ---
st.markdown('<h1 style="text-align:center; font-size:40px;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search_in = st.text_input("", placeholder="🔍 חפש מוצר (למשל: TVC7056)...")

# --- פילטרים בצד ---
with st.sidebar:
    st.header("⚙️ סינון")
    max_price = st.slider("מחיר מקסימלי (USD)", 0.0, 30.0, 30.0)
    max_moq = st.number_input("MOQ מקסימלי", value=10000)
    if st.session_state.selected_items:
        st.success(f"בסל: {len(st.session_state.selected_items)}")
        if st.button("🗑️ נקה סל"): st.session_state.selected_items = {}; st.rerun()

if not df.empty and search_in:
    service = get_service()
    term = normalize_text(search_in)
    term_en = normalize_text(transform_he_to_en(search_in))
    res = df[df['normalized_text'].str.contains(term) | df['normalized_text'].str.contains(term_en)].copy()
    
    # הפעלת פילטרים
    res = res[(res['price'].fillna(0) <= max_price) & (res['moq'].fillna(0) <= max_moq)]

    if not res.empty:
        res = res.drop_duplicates(subset=['item_no'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(res.iterrows()):
            u_id = f"{row['base_filename']}_{row['row_idx']}"
            with cols[i % 4]:
                # התאמת תמונה מדויקת לפי שם קובץ ומספר שורה
                target_img_name = f"{row['base_filename']}_row_{row['row_idx']}.jpg"
                img_id = img_map.get(target_img_name) or img_map.get(row['base_filename'] + ".jpg")
                
                img_b64 = get_img_b64(service, img_id) if img_id else None
                
                # בניית תוכן הקובייה
                st.markdown(f'<div class="product-card">', unsafe_allow_html=True)
                
                # צ'קבוקס בחירה
                if st.checkbox("בחר", key=f"sel_{u_id}", value=u_id in st.session_state.selected_items):
                    st.session_state.selected_items[u_id] = row
                
                # תמונה
                if img_b64:
                    st.markdown(f'<div class="img-container"><img src="data:image/jpeg;base64,{img_b64}"></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="img-container" style="color:#ccc;">📷 אין תמונה</div>', unsafe_allow_html=True)
                
                # כותרת ותגיות
                st.markdown(f"**{row['item_no']}**", unsafe_allow_html=True)
                tags = ""
                if row['moq']: tags += f'<span class="moq-tag">📦 MOQ: {row['moq']}</span>'
                if row['capacity']: tags += f'<span class="cap-tag">💧 {row['capacity']}</span>'
                st.markdown(f'<div style="margin:5px 0;">{tags}</div>', unsafe_allow_html=True)
                
                # פירוט טקסטואלי (ניקוי כפילויות)
                st.markdown('<div class="details-container">', unsafe_allow_html=True)
                for detail in row['display_list']:
                    d_up = detail.upper()
                    if not contains_chinese(detail) and not any(x in d_up for x in ['ITEM NO', 'ITEM REF', 'WEB', 'HTTP', 'FOB PORT']):
                        if 'USD' in d_up: 
                            st.markdown(f'<div class="price-line">💰 {detail}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f"• {detail}")
                st.markdown('</div></div>', unsafe_allow_html=True)
