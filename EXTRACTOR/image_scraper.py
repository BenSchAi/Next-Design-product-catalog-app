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
    """חילוץ תמונות מקובץ XLS ישן בשיטה הקלאסית"""
    import xlrd
    images = []
    try:
        # פתיחת הספר עם מידע על פורמט ותמונות
        book = xlrd.open_workbook(file_contents=file_content, formatting_info=True)
        # בפורמט XLS, התמונות שמורות בזיכרון של הספר תחת המאפיין biff_records
        for sheet_idx in range(book.nsheets):
            sheet = book.sheet_by_index(sheet_idx)
            # חיפוש תמונות ב-drawing records של ה-sheet
            if hasattr(book, 'handle_shared_resources'):
                for biff_record in book.biff_records:
                    # קוד 0x01B6 או 0x00EB הם בדרך כלל רשומות של תמונות (MSODRAWING)
                    if biff_record[0] in [0x01B6, 0x00EB, 0x00E0]:
                        try:
                            img = Image.open(io.BytesIO(biff_record[1]))
                            images.append(img)
                        except:
                            continue
    except Exception as e:
        print(f"  ⚠️ שגיאת XLS פנימית: {e}")
    return images

def process_excels():
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    service = get_service()
    if not service: return
    
    results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(name)").execute()
    existing_imgs = [f['name'].lower() for f in results.get('files', [])]

    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    excels = results.get('files', [])

    for excel in excels:
        file_name = excel['name']
        file_id = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        
        if any(base_name.lower() in n for n in existing_imgs):
            print(f"✅ '{file_name}' כבר קיים. מדלג...")
            continue
            
        print(f"🔄 שואב תמונות מתוך: {file_name}")
        
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            content = fh.getvalue()
            
            found_images = []

            # טיפול ב-XLS ישן (כמו הקבצים ששלחת עכשיו)
            if file_name.lower().endswith('.xls'):
                found_images = extract_images_from_xls(content)
                
            # טיפול ב-XLSX חדש
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
                print(f"  📸 הועלתה: {new_img_name}")
                
        except Exception as e:
            print(f"❌ שגיאה ב-{file_name}: {e}")

if __name__ == "__main__":
    process_excels()
