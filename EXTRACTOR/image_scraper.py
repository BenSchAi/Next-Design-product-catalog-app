import io
import base64
import json
import tempfile
import os
import sys

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

def empty_robot_trash(service):
    print("🧹 מנקה את 'פח האשפה' והאחסון הנסתר של הרובוט...")
    try:
        service.files().emptyTrash().execute()
        page_token = None
        deleted = 0
        while True:
            # שולף רק קבצים שהרובוט יצר בעצמו
            results = service.files().list(
                q="'me' in owners", 
                fields="nextPageToken, files(id, parents)", 
                pageToken=page_token,
                pageSize=1000
            ).execute()
            
            for f in results.get('files', []):
                parents = f.get('parents', [])
                # מוחק כל מה שלא יושב פיזית בתיקיית התמונות הנוכחית שלך
                if FOLDER_ID_IMAGES not in parents:
                    try:
                        service.files().delete(fileId=f['id']).execute()
                        deleted += 1
                    except:
                        pass
            
            page_token = results.get('nextPageToken')
            if not page_token or deleted > 3000: 
                break
                
        if deleted > 0:
            print(f"✅ המקום התפנה לחלוטין! נמחקו {deleted} קבצי רפאים נסתרים.")
        else:
            print("✅ אחסון הרובוט נקי.")
    except Exception as e:
        print(f"⚠️ שגיאה בניקוי פנימי: {e}")

def process_excels():
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    from spire.xls import Workbook
    
    service = get_service()
    if not service: return
    
    # שלב קריטי: פינוי ה-15GB של הרובוט לפני העבודה
    empty_robot_trash(service)
    
    results = service.files().list(q=f"'{FOLDER_ID_IMAGES}' in parents", fields="files(name)").execute()
    existing_imgs = [f['name'].lower() for f in results.get('files', [])]

    results = service.files().list(q=f"'{FOLDER_ID_EXCELS}' in parents", fields="files(id, name)").execute()
    excels = results.get('files', [])

    print(f"סורק {len(excels)} קבצי אקסל בדרייב...")

    for excel in excels:
        file_name = excel['name']
        file_id = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        
        print(f"--- שואב באמצעות Spire.Xls מהקובץ: {file_name} ---")
        
        try:
            request = service.files().get_media(fileId=file_id)
            ext = file_name.rsplit('.', 1)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp_excel:
                downloader = MediaIoBaseDownload(tmp_excel, request)
                done = False
                while not done: _, done = downloader.next_chunk()
                tmp_excel_path = tmp_excel.name

            workbook = Workbook()
            workbook.LoadFromFile(tmp_excel_path)
            
            img_counter = 0
            for sheet_idx in range(workbook.Worksheets.Count):
                sheet = workbook.Worksheets[sheet_idx]
                for pic_idx in range(sheet.Pictures.Count):
                    pic = sheet.Pictures[pic_idx]
                    
                    img_name = f"{base_name}_{img_counter}.png"
                    if img_name.lower() in existing_imgs:
                        print(f"  ✅ התמונה {img_name} כבר קיימת.")
                        img_counter += 1
                        continue
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                        pic.Picture.Save(tmp_img.name)
                        
                        media = MediaFileUpload(tmp_img.name, resumable=True)
                        service.files().create(
                            body={'name': img_name, 'parents': [FOLDER_ID_IMAGES]},
                            media_body=media
                        ).execute()
                        print(f"  🚀 הצלחה! התמונה חולצה (Spire): {img_name}")
                    
                    os.remove(tmp_img.name)
                    img_counter += 1
            
            workbook.Dispose()
            os.remove(tmp_excel_path)
            
            if img_counter == 0:
                print(f"  ⚠️ לא נמצאו תמונות בקובץ {file_name}")
                
        except Exception as e:
            print(f"  ❌ שגיאה בקובץ {file_name}: {e}")

if __name__ == "__main__":
    process_excels()
