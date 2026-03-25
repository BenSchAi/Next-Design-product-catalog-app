import io
import base64
import json
import zipfile
import tempfile
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import sys

# מאפשר לרובוט למצוא את constants.py שנמצא בתיקייה הראשית
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import constants

FOLDER_ID_EXCELS = "1em5nttKDkBs86VgrknaKjhdNi_XBITCK"
FOLDER_ID_IMAGES = "1pIz-PszCqheMiTyBvDMvJdtpBbt1vRet"

def get_service():
    print("מתחבר ל-Google Drive...")
    encoded_key = constants.GCP_SERVICE_ACCOUNT 
    decoded_key = base64.b64decode(encoded_key).decode('utf-8')
    info = json.loads(decoded_key)
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def process_excels():
    service = get_service()
    
    # 1. משיכת רשימת התמונות הקיימות (כדי לא לשכפל)
    existing_results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(name)").execute()
    existing_names = [f['name'].lower() for f in existing_results.get('files', [])]

    # 2. משיכת קבצי האקסל
    excel_results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    excels = excel_results.get('files', [])

    if not excels:
        print("לא נמצאו קבצי אקסל בתיקייה.")
        return

    for excel in excels:
        file_name = excel['name']
        file_id = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        
        # בדיקה אם כבר יש תמונות לקובץ הזה
        if any(base_name.lower() in name for name in existing_names):
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

            # --- הטריק של Colab: שאיבת תמונות מתוך ה-ZIP של האקסל ---
            if file_name.lower().endswith('.xlsx'):
                with zipfile.ZipFile(fh) as z:
                    # חיפוש כל קבצי המדיה בתוך האקסל
                    media_files = [f for f in z.namelist() if f.startswith('xl/media/')]
                    
                    if not media_files:
                        print(f"⚠️ לא נמצאו תמונות בתוך {file_name}")
                        continue
                        
                    for idx, media_file in enumerate(media_files):
                        img_data = z.read(media_file)
                        ext = media_file.split('.')[-1]
                        
                        # יצירת שם תואם לאפליקציה (base_filename_row_X)
                        new_img_name = f"{base_name}_row_{idx}.{ext}"
                        
                        # שמירה זמנית והעלאה לדרייב
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                            tmp.write(img_data)
                            tmp_path = tmp.name
                            
                        file_metadata = {'name': new_img_name, 'parents': [FOLDER_ID_IMAGES]}
                        media = MediaFileUpload(tmp_path, resumable=True)
                        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                        os.remove(tmp_path)
                        
                        print(f"  📸 חולצה והועלתה תמונה: {new_img_name}")
                        
            elif file_name.lower().endswith('.xls'):
                print(f"⚠️ הערה: הקובץ {file_name} הוא בפורמט XLS ישן. מומלץ לשמור אותו כ-XLSX כדי שהרובוט יוכל לשאוב ממנו תמונות.")
                
        except Exception as e:
            print(f"❌ שגיאה בשאיבה מהקובץ {file_name}: {e}")

if __name__ == "__main__":
    process_excels()
    print("המשימה הושלמה!")
