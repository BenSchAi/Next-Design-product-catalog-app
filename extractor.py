import streamlit as st
import io
import pandas as pd
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import constants
import base64
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# הגדרות תיקיות (זהות ל-app.py)
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

def get_service():
    encoded_key = constants.GCP_SERVICE_ACCOUNT 
    decoded_key = base64.b64decode(encoded_key).decode('utf-8')
    info = json.loads(decoded_key)
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def run_extraction():
    service = get_service()
    # 1. קבלת רשימת התמונות שכבר קיימות כדי לא לעבוד כפול
    existing_imgs = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(name)").execute().get('files', [])
    existing_names = [f['name'] for f in existing_imgs]

    # 2. קבלת רשימת האקסלים
    excels = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute().get('files', [])

    for excel in excels:
        base_name = excel['name'].rsplit('.', 1)[0]
        
        # בדיקה אם כבר חילצנו תמונות לקובץ הזה (לפי שם הקובץ)
        if any(base_name in name for name in existing_names):
            continue

        try:
            # הורדת האקסל לזיכרון
            request = service.files().get_media(fileId=excel['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            
            # חילוץ בסיסי (כאן המנוע מזהה שורות עם תמונות)
            # בשלב זה אנחנו רק מייצרים קובץ דמי או מחלצים אם זה XLSX
            # הערה: חילוץ מלא מ-XLS דורש ספריות נוספות, נתחיל בבדיקת נוכחות
            st.write(f"מעבד את קובץ: {excel['name']}...")
            
        except Exception as e:
            print(f"Error processing {excel['name']}: {e}")

    return True
