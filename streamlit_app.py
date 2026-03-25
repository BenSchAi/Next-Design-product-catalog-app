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
        padding: 15px 20px !important; font-size: 16px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
    }

    /* תיקון קוביות המוצר - גובה גמיש כדי שהתמונות יופיעו */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px !important; border: 1px solid #f0f0f0 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03) !important;
        background-color: white; padding: 15px !important; 
        position: relative;
        min-height: auto !important;
        max-height: none !important;
        overflow: visible !important;
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

# --- חיבור לגוגל ---
def get_gdrive_service():
    try:
        raw_key = "ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAiZ2VuLWxhbmctY2xpZW50LTA0MDA3MjU1ODAiLAogICJwcml2YXRlX2tleV9pZCI6ICIyMjc5M2YyMGRlMjdhZjc5NmUzZWRiZGYzMTA5NzdkYzU1NTFhOGVjIiwKICAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tXG5NSUlFdkFJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLWXdnZ1NpQWdFQUFvSUJBUURKY1BXeXc5S2lxMmlRXG5OazA3bDNwQkNGR3hNTTJubU80eW1XWUh1d2NtTkhuMjdacThaOW5HVTFYMmdyejFlRUhQaDQrRTVIcTE2bVdDXG5UYmQ0RkNRWlRTcE1ad1duelFMS3I1cWlJa09hYkdBTllYS2RZdjhBWmIwUk9zSWNiYlBETGNuYzFHUEprcTJKXG5pQk9pc2NKKzV1SHFnMUVUZkxKSVZja3NwUjFjVm43c2ZIQWF2Ujl4NzY2VFdlb3RLNGpZTWxyRTdlaEY5UEQvXG52aUdkQlY4Z2laNC9ocXh3TUttNmpkVnBuNDBac0hJd0xid0txS3liMHJqdmRHVmo5c0F2dUl1NW1Dd0RYNWNNXG5vV0FCc3VkejVMN2hEd05FYndEU3NCRmpvK0FBSlhvSFBPNjJqZTZ2bWk1c21ZMmlOTGl3VXNodG5BR3pGRURYXG45clZOUlMrRkFnTUJBQUVDZ2dFQVZtV3M4N1c2WjB1R0p1Z3JXdVkrcUpyVlV0NkFMaVJROFlIS2VZRlZjU1RyXG50S1UzQ3h5dGtqclc4VW9rbWxHd1JENjdwdjlKeERGYXhUYm8vRWNETHBqaWplOVh4UjhRVmZkWUpyYjBjTXlQXG5xOTJDUjQrWW1FYUtmMVBJd21Hb3lvc2VlNmphZmE5NzM3TnQzSWRLU0p4bEEreTdmdFNxTUkwZW9oZlZUbThFXG40aWMrTmpuL2pUcHdEbEY3TDROOXI1WUpKUGd6WkRnRy81RUN3cko4V09ETUk2bng4N1Z1alkzU3FGbjFoMzNXXG5CS1lXazJvTHZobmZvY2xJUVdjODl1bkYvWnNWaXVYN1ltcWpTLzFpeXBvWVZJK3EweEMzL3pFTEU3N1ZLelBUXG5iaEpseCtXUnE5RDkwcnVPQ1N1Mm9mYmdLYmFhenZ6MUF0VTg1aHo4RndLQmdRRDdsZkgyak5Xa2VLeS9rUTZ2XG5jdGwwdFl0R3ptbFZMSWVxdmRCVkxQcmllTmlsWG55VHpweFFaU3N4b01CaHNNdDlnY0VUVysyRTZiVWhNTzNPXG5VZzgzSVJsUWRDRks3N2dyZVNpTmMxaGVpdTdIdkNxaGNNeXNLczJYaUpzcGdnTUpHcGYwZTB3TDNJMTZhb053XG52ZGh2VHlacjVGbG1rdk0zZ1dJdlJabmsrd0tCZ1FETStjZDZnSFI2QXNHVjNKMlRUdHZkZlVDd1NpcnZSZTZFXG5scjlnLzVWRFY2WHNyek82K3pIR2dHSWRPbGVEY3M4bHkwV050TGF3NEl0L0JUSlpiSGN2aDBOZ3lDNFY3Ry9FXG5EOERycTBTODR4RzUwM1R6dmM2endnQVFaRlRXMTZ2S2hXQVZxbE5UanhRUXV2QnVzdHo0SHNuRldyVi9hUXZkXG5ydGt5Y1N3VmZ3S0JnQ2cyT0QxckZ6NjVsd3JyZVlocmQveGloQWRtT0luSG0wdWNHUzkwQ0Ftb3ZSLzVjVG9DXG52Uk5RaUUzZlhzQitqSmZiNUd0ZXR5RVdaY0FQWFFNc05JaGdQdmFRQ1Q0OEFKamFQYlFXS3BxNTVCNkNvZUc1XG44TXpYN3BKNDRDd0xQc2IydkREMGdCd3BQV2ZDbkkycG1tMTRIakVDaDVPUWkxVmsxYmV1alVGL0FvR0FIN09oXG4vbmhQaTI5UnNYUGxpeHJ2TmxwZzN1TVpzTmdJQThtczM3dW53anFVRnY4aDZSRmdxV3JCd2ZOOEJZQ0VPVHd2XG5EYk9kYmMzTXhXQndZUlE5ZXNSWXoyY21lWTJQMjZyMEUzN3hxcVVUNE1Hcm5PY0dTUmNBRzRqbzlqRjFDR1dJXG5idEZoQWRObkx3ODZrR1JwZUphS2JsT1JMcHQ0a2xpd2p2U2g5TkVDZ1lBWmhuWFdDUkJGTTI5UlpxK3VxdmM2XG5FcDR4b0lxUWprRkYreGlLWTVacmlzQUt5bDNmVXcrMnR4ZDhxWE5DdHBqK3psdzRlQ210ZjNVM282UU1UM0VVXG52VGp5RlA2Qi9jMDYvTkFubVQrUEo3THBaNWoxWFZXVTB5WnZwZjlHdlVNVnJWZGpMeVRJdGs2alZlTzZLNW1zXG5BMS9uNGdZSkZMR0RRMmFybzdUTENBPT1cbi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS1cbiIsCiAgImNsaWVudF9lbWFpbCI6ICJkcml2ZS1yb2JvdEBnZW4tbGFuZy1jbGllbnQtMDQwMDcyNTU4MC5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsCiAgImNsaWVudF9pZCI6ICIxMDkxNzM5OTUzNzQwNTIwMTMxNzUiLAogICJhdXRoX3VyaSI6ICJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0aDIvYXV0aCIsCiAgInRva2VuX3VyaSI6ICJodHRwczovL29hdXRoMi5nb29nbGVhcGlzLmNvbS90b2tlbiIsCiAgImF1dGhfcHJvdmlkZXJfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9vYXV0aDIvdjEvY2VydHMiLAogICJjbGllbnRfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9yb2JvdC92MS9tZXRhZGF0YS94NTA5L2RyaXZlLXJvYm90JTQwZ2VuLWxhbmctY2xpZW50LTA0MDA3MjU1ODAuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLAogICJ1bml2ZXJzZV9kb21haW4iOiAiZ29vZ2xlYXBpcy5jb20iCn0K" # <--- תדביק כאן את ה-BASE64 שלך
        encoded_key = re.sub(r'[^A-Za-z0-9+/=]', '', raw_key)
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
            df_excel = pd.read_excel(fh, header=None, engine='xlrd' if item['name'].endswith('.xls') else None)
            
            skip_until = -1
            for idx in range(len(df_excel)):
                if idx < skip_until: continue
                row_str = " ".join(df_excel.iloc[idx].dropna().astype(str))
                if any(k in row_str.upper() for k in ['ITEM NO', 'ITEM REF', 'ITEM:', 'DESCRIPTION']):
                    details = []
                    item_key = ""
                    for offset in range(25):
                        curr_idx = idx + offset
                        if curr_idx >= len(df_excel): break
                        line = " ".join(df_excel.iloc[curr_idx].dropna().astype(str)).strip()
                        if offset > 1 and any(k in line.upper() for k in ['ITEM NO', 'ITEM REF']): break
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
    max_moq = st.number_input("MOQ מקסימלי", value=0, min_value=0)
    max_delivery = st.slider("זמן אספקה מקסימלי (ימים)", 5, 90, 90, 5)
    
    available_materials = ["Stainless Steel", "Plastic", "Bamboo", "Glass", "Silicone", "Ceramic"]
    available_capacities = sorted([c for c in df['capacity'].unique() if c]) if not df.empty else []
    
    selected_materials = st.multiselect("חומר", available_materials)
    selected_capacities = st.multiselect("נפח", available_capacities)
    
    st.divider()
    st.header("🛒 סל מוצרים")
    if st.session_state.selected_items:
        st.success(f"נבחרו {len(st.session_state.selected_items)} מוצרים")
        email_body = "שלום,\n\nלהלן פרטי המוצרים:\n\n"
        for item_id, item_data in st.session_state.selected_items.items():
            email_body += f"--- {item_data['item_key']} ---\n"
            for detail in item_data['display_list']:
                if not contains_chinese(detail): email_body += f"• {detail}\n"
            email_body += "\n"
        encoded_subject = urllib.parse.quote("Next Design - פרטי מוצרים")
        encoded_body = urllib.parse.quote(email_body)
        st.markdown(f'<a href="mailto:?subject={encoded_subject}&body={encoded_body}" class="email-btn" target="_blank">✉️ שלח במייל</a>', unsafe_allow_html=True)
        if st.button("🗑️ נקה סל"):
            st.session_state.selected_items = {}
            st.rerun()

st.markdown('<h1 style="text-align:center;">NEXT DESIGN</h1>', unsafe_allow_html=True)
search_input = st.text_input("", placeholder="🔍 חפש מוצר...")

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
        results = results.drop_duplicates(subset=['item_key', 'file_source'])
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
                        if b64: st.markdown(f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; height:200px; object-fit:contain; border-radius:8px; margin-bottom:10px;">', unsafe_allow_html=True)
                    
                    st.write(f"**{row['item_key']}**")
                    tags = ""
                    if row['moq']: tags += f"<span style='background:#f1c40f; padding:2px 5px; border-radius:4px; font-size:11px;'>📦 MOQ: {row['moq']}</span> "
                    if row['capacity']: tags += f"<span style='background:#eee; padding:2px 5px; border-radius:4px; font-size:11px;'>💧 {row['capacity']}</span>"
                    st.markdown(tags, unsafe_allow_html=True)
                    
                    for detail in row['display_list']:
                        d_up = detail.upper()
                        # סינון כפילויות של ITEM NO ו-MOQ מגוף הטקסט
                        if not contains_chinese(detail) and not any(x in d_up for x in ['ITEM NO', 'MOQ:', 'FOB COST', 'FOB PORT', 'WEB', 'HTTP', 'VALIDITY']):
                            if 'USD' in d_up: st.write(f"<span style='color:#27ae60; font-weight:bold;'>💰 {detail}</span>", unsafe_allow_html=True)
                            elif 'DELIVERY' in d_up or 'DAYS' in d_up: st.write(f"<small>🚚 {detail}</small>", unsafe_allow_html=True)
                            else: st.write(f"<small>• {detail}</small>", unsafe_allow_html=True)
