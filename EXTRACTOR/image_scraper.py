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

def extract_images_from_binary(content):
    """נשק יום הדין: סורק את הביטים של הקובץ ומחלץ תמונות בכוח, עוקף כל תלות בספריית אקסל"""
    images = []
    
    # חיפוש חתימות דיגיטליות של תמונות JPEG
    idx = 0
    while True:
        idx = content.find(b'\xff\xd8\xff', idx)
        if idx == -1: break
        # חותך בלוק גדול מתוך הקובץ (מכיל את התמונה)
        chunk = content[idx:idx+10000000]
        try:
            img = Image.open(io.BytesIO(chunk))
            img.load() # מוודא שהתמונה תקינה
            # מסנן אייקונים זעירים של אקסל
            if img.width > 50 and img.height > 50:
                images.append(img.copy())
            idx += 1000 # מדלג קדימה כדי לא לחתוך את אותה תמונה שוב
        except:
            idx += 3

    # חיפוש חתימות דיגיטליות של תמונות PNG
    idx = 0
    while True:
        idx = content.find(b'\x89PNG\r\n\x1a\n', idx)
        if idx == -1: break
        chunk = content[idx:idx+10000000]
        try:
            img = Image.open(io.BytesIO(chunk))
            img.load()
            if img.width > 50 and img.height > 50:
                images.append(img.copy())
            idx += 1000
        except:
            idx += 8
            
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
            
        print(f"🔄 גלאי מתכות מופעל על הקובץ: {file_name}")
        
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            content = fh.getvalue()
            
            found_images = []

            # אם זה קובץ XLSX חדש, נשתמש בשיטה הבטוחה של ה-ZIP
            if file_name.lower().endswith('.xlsx'):
                try:
                    import zipfile
                    with zipfile.ZipFile(io.BytesIO(content)) as z:
                        media_files = [f for f in z.namelist() if f.startswith('xl/media/')]
                        for mf in media_files:
                            found_images.append(Image.open(io.BytesIO(z.read(mf))))
                except:
                    pass
            
            # אם זה XLS ישן (או שהראשון כשל), נפעיל את חולץ הביטים!
            if not found_images:
                found_images = extract_images_from_binary(content)

            if not found_images:
                print(f"⚠️ לא נמצאו תמונות ב-{file_name}")
                continue
                
            for idx, img in enumerate(found_images):
                ext = img.format.lower() if img.format else "png"
                if ext == 'jpeg': ext = 'jpg'
                new_img_name = f"{base_name}_row_{idx}.{ext}"
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                    img.save(tmp.name)
                    media = MediaFileUpload(tmp.name, resumable=True)
                    service.files().create(body={'name': new_img_name, 'parents': [FOLDER_ID_IMAGES]}, media_body=media).execute()
                print(f"  📸 הצלחה! תמונה חולצה מהביטים: {new_img_name}")
                
        except Exception as e:
            print(f"❌ שגיאה ב-{file_name}: {e}")

if __name__ == "__main__":
    process_excels()
