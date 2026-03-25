import io
import base64
import json
import tempfile
import os
import sys
from PIL import Image

# הזרקת נתיב constants
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import constants

# הגדרות תיקיות מדרייב
FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

def get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    encoded_key = constants.GCP_SERVICE_ACCOUNT 
    decoded_key = base64.b64decode(encoded_key).decode('utf-8')
    info = json.loads(decoded_key)
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def extract_images_from_xls(file_content):
    """חילוץ תמונות מ-XLS ישן בשיטת ה-COLAB המוכחת"""
    import xlrd
    images = []
    try:
        # פתיחה עם formatting_info חובה לזיהוי אובייקטים
        book = xlrd.open_workbook(file_contents=file_content, formatting_info=True)
        # שאיבה ישירה של ה-Bitmaps מה-BIFF records
        for biff_record in book.biff_records:
            # 0x00E0/0x01B6 הם הקודים לתמונות מוטמעות (MSODRAWING)
            if biff_record[0] in [0x00E0, 0x01B6, 0x00EB]:
                try:
                    data = biff_record[1]
                    # ניסיון פענוח ישיר כ-Image
                    img = Image.open(io.BytesIO(data))
                    images.append(img)
                except:
                    continue
    except Exception as e:
        print(f"  ⚠️ ניסיון חילוץ XLS נכשל: {e}")
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

    for excel in excels:
        file_name = excel['name']
        file_id = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        
        # דילוג על מה שכבר קיים
        if any(base_name.lower() in n for n in existing_imgs):
            print(f"✅ '{file_name}' כבר עובד. מדלג...")
            continue
            
        print(f"🔄 רובוט COLAB שואב מתוך: {file_name}")
        
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            content = fh.getvalue()
            
            found_images = []

            # שאיבת XLS ישן
            if file_name.lower().endswith('.xls'):
                found_images = extract_images_from_xls(content)
            
            # שאיבת XLSX חדש
            elif file_name.lower().endswith('.xlsx'):
                import zipfile
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    media_files = [f for f in z.namelist() if f.startswith('xl/media/')]
                    for mf in media_files:
                        found_images.append(Image.open(io.BytesIO(z.read(mf))))

            if not found_images:
                print(f"⚠️ לא נמצאו תמונות ב-{file_name}")
                continue
                
            for idx, img in enumerate(found_images):
                ext = img.format.lower() if img.format else "png"
                new_img_name = f"{base_name}_row_{idx}.{ext}"
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    img.save(tmp.name)
                    media = MediaFileUpload(tmp.name, resumable=True)
                    service.files().create(body={'name': new_img_name, 'parents': [FOLDER_ID_IMAGES]}, media_body=media).execute()
                print(f"  📸 הצלחה! חולצה תמונה: {new_img_name}")
                
        except Exception as e:
            print(f"❌ שגיאה ב-{file_name}: {e}")

if __name__ == "__main__":
    process_excels()
