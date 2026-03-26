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

# --- הגדרות קבועות ---
FOLDER_ID_EXCELS = "1x7bE0YmGhrK_-0f06ixwlOKqquV_8AHZ"
FOLDER_ID_IMAGES = "1R4nm5cf2NEWB30IceF4cL5oShNlqurPS"

# אתחול ה-Session State לבחירת מוצרים אם לא קיים
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
    }
    .email-btn {
        display: block; width: 100%; text-align: center; background-color: #27ae60;
        color: white !important; padding: 12px; border-radius: 8px; text-decoration: none;
        font-weight: bold; margin-top: 15px; margin-bottom: 10px;
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

# --- פונקציות עזר וסריקה ---
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
                    val = float(match); prices.append(val) if val > 0 else None
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

def get_gdrive_service():
    try:
        encoded_key = constants.GCP_SERVICE_ACCOUNT 
        decoded_key = base64.b64decode(encoded_key).decode('utf-8')
        info = json.loads(decoded_key)
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except: return None

@st.cache_data(ttl=3600)
def get_image_base64(_service, file_id):
    try:
        request = _service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request); done = False
        while not done: _, done = downloader.next_chunk()
        return base64.b64encode(fh.getvalue()).decode('utf-8')
    except: return None

@st.cache_data(ttl=600)
def load_all_data():
    service = get_gdrive_service()
    if not service: return pd.DataFrame(), {}
    
    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    all_products = []
    
    for item in results.get('files', []):
        try:
            request = service.files().get_media(fileId=item['id'], supportsAllDrives=True)
            fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request); done = False
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
                        if line and not any(x in line.upper() for x in ['WEB', 'HTTP']):
                            details.append(line)
                            if 'ITEM' in line.upper() and not item_key: item_key = line
                    else: skip_until = idx + 25
                    if details:
                        all_products.append({
                            'item_key': item_key if item_key else details[0],
                            'display_list': details,
                            'normalized_text': normalize_text(" ".join(details)),
                            'file_source': item['name'],
                            'base_filename': item['name'].rsplit('.', 1)[0],
                            'row_index': idx,
                            'min_price': extract_min_price(details),
                            'moq': extract_moq(details)
                        })
        except: continue
    
    img_results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    img_map = {f['name']: f['id'] for f in img_results.get('files', [])}
    return pd.DataFrame(all_products), img_map

df, img_map = load_all_data()

# --- תפריט צד (סינונים וסל קניות) ---
with st.sidebar:
    st.header("⚙️ סינון חכם")
    price_min, price_max = st.slider("טווח מחיר ליח' (USD)", 0.0, 30.0, (0.0, 30.0), 0.1)
    max_moq = st.number_input("MOQ מקסימלי", 0, 100000, 50000)
    
    # הצגת סל הקניות רק אם יש מוצרים
    if st.session_state.selected_items:
        st.divider()
        st.header(f"🛒 נבחרו {len(st.session_state.selected_items)} מוצרים")
        
        # בניית גוף המייל
        email_body = "שלום,\n\nלהלן המוצרים שבחרתי מהקטלוג:\n\n"
        for i_id, item in st.session_state.selected_items.items():
            email_body += f"--- {item['item_key']} ---\n"
            for d in item['display_list']:
                if not contains_chinese(d): email_body += f"• {d}\n"
            email_body += f"מקור: {item['file_source']}\n\n"
        
        encoded_subject = urllib.parse.quote("Next Design - בחירת מוצרים מהקטלוג")
        encoded_body = urllib.parse.quote(email_body)
        
        # כפתור שליחה למייל
        st.markdown(f'<a href="mailto:?subject={encoded_subject}&body={encoded_body}" class="email-btn" target="_blank">✉️ שלח רשימה במייל</a>', unsafe_allow_html=True)
        
        if st.button("🗑️ נקה רשימה", use_container_width=True):
            st.session_state.selected_items = {}
            st.rerun()

# --- חיפוש ותצוגה ---
search_input = st.text_input("", placeholder="🔍 הקלד שם מוצר לחיפוש (למשל: Bottle)...")

if not df.empty:
    service = get_gdrive_service()
    
    # סינון הנתונים
    results = df.copy()
    if search_input:
        term = normalize_text(search_input)
        results = results[results['normalized_text'].str.contains(term, na=False)]
    
    # החלת פילטרים מהסרגל
    if price_min > 0.0 or price_max < 30.0:
        results = results[results['min_price'].apply(lambda x: x is not None and price_min <= x <= price_max)]
    if max_moq < 50000:
        results = results[results['moq'].apply(lambda x: x is None or x <= max_moq)]

    if not results.empty:
        results = results.drop_duplicates(subset=['item_key', 'file_source'])
        cols = st.columns(4)
        for i, (_, row) in enumerate(results.iterrows()):
            unique_id = f"{row['base_filename']}_{row['row_index']}"
            with cols[i % 4]:
                with st.container(border=True):
                    # ניהול בחירת מוצר - תיקון הספירה
                    is_selected = st.checkbox("➕ בחר", value=(unique_id in st.session_state.selected_items), key=f"chk_{unique_id}")
                    if is_selected:
                        st.session_state.selected_items[unique_id] = row
                    else:
                        st.session_state.selected_items.pop(unique_id, None)

                    # לוגיקת תמונה
                    img_id = None
                    base_n = normalize_text(row['base_filename'])
                    valid_imgs = {n: i_id for n, i_id in img_map.items() if base_n in normalize_text(n)}
                    if valid_imgs:
                        row_t = f"row_{row['row_index']}"
                        for name, i_id in valid_imgs.items():
                            if row_t in normalize_text(name): img_id = i_id; break
                        if not img_id: img_id = list(valid_imgs.values())[0]
                    
                    img_html = '<div style="color:#aaa; font-size:12px; height:200px; display:flex; align-items:center; justify-content:center;">📷 אין תמונה</div>'
                    if img_id:
                        img_b64 = get_image_base64(service, img_id)
                        if img_b64:
                            img_html = f'<div style="height:200px; display:flex; align-items:center; justify-content:center;"><img src="data:image/jpeg;base64,{img_b64}" style="max-width:100%; max-height:100%; object-fit:contain; border-radius:4px;"></div>'

                    st.markdown(f"""
                        <div style="height: 580px; display: flex; flex-direction: column;">
                            {img_html}
                            <div style="margin-top:10px; margin-bottom:5px;">
                                {f"<span style='background:#f1c40f; padding:2px 5px; border-radius:4px; font-size:10px; font-weight:bold;'>MOQ: {row['moq']}</span>" if row['moq'] else ""}
                            </div>
                            <div style="flex-grow:1; overflow-y:auto; font-size:13px; text-align:left; line-height:1.4;">
                                {''.join([f"<div style='margin-bottom:2px;'>• {d}</div>" for d in row['display_list'] if not contains_chinese(d)])}
                            </div>
                            <div style="border-top:1px solid #eee; padding-top:5px; font-size:10px; color:#aaa; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;">📂 {row['file_source']}</div>
                        </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("לא נמצאו תוצאות לחיפוש או לסינונים שבחרת.")
