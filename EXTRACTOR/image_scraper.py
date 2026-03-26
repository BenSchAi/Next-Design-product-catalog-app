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

def extract_images_direct(content):
    """חילוץ תמונות ישירות מהביטים של הקובץ - עוקף את כל שגיאות האקסל"""
    found = []
    # חתימות דיגיטליות של JPEG ו-PNG
    signatures = [
        (b'\xff\xd8\xff', b'\xff\xd9'), # JPEG
        (b'\x89PNG\r\n\x1a\n', b'IEND\xaeB`\x82') # PNG
    ]
    
    for start_sig, end_sig in signatures:
        start = 0
        while True:
            start = content.find(start_sig, start)
            if start == -1: break
            
            end = content.find(end_sig, start)
            if end == -1:
                # אם אין סוף ברור, ניקח נתח גדול וננסה לפענח
                end = start + 5000000 
            else:
                end += len(end_sig)
            
            try:
                img_data = content[start:end]
                img = Image.open(io.BytesIO(img_data))
                img.load()
                # מסנן רק תמונות שאינן אייקונים קטנים
                if img.width > 40 and img.height > 40:
                    found.append(img.copy())
                start = end
            except:
                start += len(start_sig)
    return found

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
        
        print(f"--- סורק קובץ (בשיטה ישירה): {file_name} ---")
        
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            content = fh.getvalue()
            
            # שאיבה ישירה בלי להשתמש בספריות אקסל בכלל!
            found_images = extract_images_direct(content)

            if not found_images:
                print(f"  ⚠️ לא נמצאו תמונות ב-{file_name}")
                continue

            for idx, img in enumerate(found_images):
                img_name = f"{base_name}_{idx}.png"
                if img_name.lower() in existing_imgs:
                    print(f"  ✅ {img_name} כבר קיים.")
                    continue

                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    img.save(tmp.name, format="PNG")
                    media = MediaFileUpload(tmp.name, resumable=True)
                    service.files().create(
                        body={'name': img_name, 'parents': [FOLDER_ID_IMAGES]},
                        media_body=media
                    ).execute()
                    print(f"  🚀 הצלחה! תמונה נשלפה מהקוד: {img_name}")
                
        except Exception as e:
            print(f"  ❌ שגיאה ב-{file_name}: {e}")

if __name__ == "__main__":
    process_excels()
