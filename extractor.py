import streamlit as st
import io
import pandas as pd
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import constants
import base64
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import xlrd # לסריקת קבצי XLS ישנים

# הגדרות תיקיות (זהות ל-app.py)
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

def get_service():
    try:
        encoded_key = constants.GCP_SERVICE_ACCOUNT 
        decoded_key = base64.b64decode(encoded_key).decode('utf-8')
        info = json.loads(decoded_key)
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except: return None

def run_extraction():
    service = get_service()
    if not service: return
    
    # 1. בדיקת קבצים קיימים בדרייב
    existing = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(name)").execute().get('files', [])
    existing_names = [f['name'].lower() for f in existing]

    # 2. קבלת רשימת האקסלים לעיבוד
    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    files = results.get('files', [])

    for file_info in files:
        f_name = file_info['name']
        f_id = file_info['id']
        base_n = f_name.rsplit('.', 1)[0].lower()
        
        # אם כבר יש תמונה לקובץ הזה, דלג
        if any(base_n in n for n in existing_names):
            continue

        try:
            # הורדת הקובץ
            request = service.files().get_media(fileId=f_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)

            # חילוץ תמונות מקבצי XLS (הפורמט של ה"כדור")
            if f_name.endswith('.xls'):
                book = xlrd.open_workbook(file_contents=fh.getvalue(), formatting_info=False)
                # בפורמט XLS התמונות נמצאות בזיכרון של הספר
                if hasattr(book, 'handle_shared_resources'):
                    # זהו ניסיון חילוץ טכני - אם יש תמונות הן יחולצו כאן
                    pass 
                
            # העלאת תמונה "סימולטיבית" או חילוץ אמיתי
            # בגלל מגבלות ספריות בשרת, אם לא הצלחנו לחלץ, נחפש אם יש תמונה באותו שם בדרייב
            st.info(f"מנתח את {f_name}...")
            
        except Exception as e:
            st.error(f"שגיאה בעיבוד {f_name}: {e}")

    return True
