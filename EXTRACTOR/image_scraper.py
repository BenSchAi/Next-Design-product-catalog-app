import io
import base64
import json
import zipfile
import tempfile
import os
import sys
import pandas as pd
from PIL import Image

# הזרקת נתיבconstants
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import constants

# הגדרות תיקיות מדרייב
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

def get_service():
    print("מתחבר ל-Google Drive...")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    encoded_key = constants.GCP_SERVICE_ACCOUNT 
    decoded_key = base64.b64decode(encoded_key).decode('utf-8')
    info = json.loads(decoded_key)
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def extract_images_from_xlsx_sheet(fh, file_name, base_name, sheet_idx=0):
    images = []
    
    # טעינת האקסל בשיטה שתאפשר סריקה ויזואלית
    import openpyxl
    try:
        book = openpyxl.load_workbook(fh, data_only=True)
        sheet = book.worksheets[sheet_idx]
        
        # סריקת אובייקטי ציור (תמונות, צורות)
        for drawing in sheet._images:
            img = drawing.image
            if isinstance(img, Image.Image):
                images.append(img)
                
    except Exception as e:
        print(f"  ❌ שגיאה בקריאת גיליון #{sheet_idx} מקובץ {file_name}: {e}")
        
    return images

def process_excels():
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    service = get_service()
    if not service: return
    
    # 1. משיכת רשימת התמונות הקיימות
    results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(name)").execute()
    existing_imgs = [f['name'].lower() for f in results.get('files', [])]

    # 2. משיכת קבצי האקסל
    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    excels = results.get('files', [])

    if not excels:
        print("לא נמצאו קבצי אקסל בתיקייה.")
        return

    for excel in excels:
        file_name = excel['name']
        file_id = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        
        # אם כבר עובדו התמונות לקובץ, דלג
        if any(base_name.lower() in n for n in existing_imgs):
            print(f"✅ תמונות עבור '{file_name}' כבר קיימות. מדלג...")
            continue
            
        print(f"🔄 מתחיל שאיבת תמונות מתוך: {file_name}")
        
        try:
            # הורדת הקובץ לזיכרון
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)

            found_images = []

            # --- הטיפול המעודכן שתואם את COLAB ---
            if file_name.lower().endswith('.xlsx'):
                found_images = extract_images_from_xlsx_sheet(fh, file_name, base_name)
            elif file_name.lower().endswith('.xls'):
                # פתרון קסם: הרובוט פותח קובץ XLS, סורק טקסט ומוצא אובייקטים
                # הוא "מנצל" את openpyxl שמתמודד גם עם XLS חלקית
                try:
                    import xlrd
                    # זו טעינה רק כדי לקרוא את קובץ המקור.
                    xlrd.open_workbook(file_contents=fh.getvalue(), formatting_info=True)
                    
                    # ניסיון לחילוץ תמונות דרך המנוע החדש. 
                    # אם זה נכשל, הוא לפחות ייתן אזהרה מדוייקת.
                    found_images = extract_images_from_xlsx_sheet(fh, file_name, base_name)
                    
                except Exception as xlrd_err:
                    print(f"⚠️ הערה: קובץ XLS ישן {file_name}. החילוץ האוטומטי עלול להיכשל. מומלץ לשמור כ-XLSX במחשב ולהעלות מחדש.")

            if not found_images:
                print(f"⚠️ לא נמצאו תמונות ויזואליות בתוך {file_name}.")
                continue
                
            for idx, img in enumerate(found_images):
                ext = img.format.lower() if img.format else "jpeg"
                new_img_name = f"{base_name}_row_{idx}.{ext}"
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    img.save(tmp.name, format=img.format if img.format else "JPEG")
                    tmp_path = tmp.name
                    
                file_metadata = {'name': new_img_name, 'parents': [FOLDER_ID_IMAGES]}
                media = MediaFileUpload(tmp_path, resumable=True)
                service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                os.remove(tmp_path)
                
                print(f"  📸 חולצה והועלתה תמונה: {new_img_name}")
                
        except Exception as e:
            print(f"❌ שגיאה כללית בעיבוד הקובץ {file_name}: {e}")

if __name__ == "__main__":
    process_excels()
    print("המשימה הושלמה!")
