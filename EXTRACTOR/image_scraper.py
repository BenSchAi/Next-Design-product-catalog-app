import io
import base64
import json
import tempfile
import os
import sys
import zipfile
from PIL import Image

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

def process_excels():
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    service = get_service()
    if not service: return
    
    results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(name)").execute()
    existing_imgs = [f['name'].lower() for f in results.get('files', [])]

    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    excels = results.get('files', [])

    print(f"סורק {len(excels)} קבצי אקסל בדרייב...")

    for excel in excels:
        file_name = excel['name']
        file_id = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        
        print(f"--- מעבד קובץ: {file_name} ---")
        
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            content = fh.getvalue()
            
            found_images = []

            # שיטה ל-XLSX
            if file_name.lower().endswith('.xlsx'):
                try:
                    with zipfile.ZipFile(io.BytesIO(content)) as z:
                        media_files = [f for f in z.namelist() if f.startswith('xl/media/')]
                        for mf in media_files:
                            img = Image.open(io.BytesIO(z.read(mf)))
                            found_images.append(img)
                except Exception as e:
                    print(f"  ⚠️ בעיה בחילוץ מ-XLSX: {e}")

            # שיטה ל-XLS ישנים (שיטת קולאב המוכחת)
            elif file_name.lower().endswith('.xls'):
                import xlrd
                book = xlrd.open_workbook(file_contents=content, formatting_info=True)
                for record in book.biff_records:
                    if record[0] in [0x00E0, 0x01B6, 0x00EB]:
                        data = record[1]
                        # חיפוש חתימות דיגיטליות למניעת קריסה
                        jpg_idx = data.find(b'\xff\xd8\xff')
                        png_idx = data.find(b'\x89PNG\r\n\x1a\n')
                        
                        try:
                            if jpg_idx != -1:
                                found_images.append(Image.open(io.BytesIO(data[jpg_idx:])))
                            elif png_idx != -1:
                                found_images.append(Image.open(io.BytesIO(data[png_idx:])))
                            else:
                                found_images.append(Image.open(io.BytesIO(data)))
                        except:
                            pass

            if not found_images:
                print(f"  ⚠️ לא נמצאו תמונות ויזואליות בקובץ {file_name}")
                continue

            for idx, img in enumerate(found_images):
                # סינון בסיסי ביותר כדי לא לתפוס פיקסלים של גבולות אקסל
                if img.width < 10 or img.height < 10:
                    continue
                    
                img_name = f"{base_name}_{idx}.png"
                if img_name.lower() in existing_imgs:
                    print(f"  ✅ התמונה {img_name} כבר קיימת.")
                    continue

                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    img.save(tmp.name, format="PNG")
                    media = MediaFileUpload(tmp.name, resumable=True)
                    service.files().create(
                        body={'name': img_name, 'parents': [FOLDER_ID_IMAGES]},
                        media_body=media
                    ).execute()
                    print(f"  🚀 הצלחה! התמונה חולצה: {img_name}")
                
        except Exception as e:
            print(f"  ❌ שגיאה בקובץ {file_name}: {e}")

if __name__ == "__main__":
    process_excels()
