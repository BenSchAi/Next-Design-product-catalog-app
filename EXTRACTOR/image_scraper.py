import io
import os
import re
import base64
import json
import tempfile
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import constants

FOLDER_ID_EXCELS = "1x7bE0YmGhrK_-0f06ixwlOKqquV_8AHZ"
FOLDER_ID_IMAGES = "1R4nm5cf2NEWB30IceF4cL5oShNlqurPS"


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
    from spire.xls import Workbook

    service = get_service()
    if not service:
        return

    # ══════════════════════════════════════════════════════════════════════
    # שלב 1 — מחיקה אוטומטית של תמונות ישנות (פורמט _0 / _1 / _2)
    # תמונה "ישנה" = שמה לא מכיל את הפטרן _row_<מספר>
    # ══════════════════════════════════════════════════════════════════════
    print(f"🔍 בודק תמונות ישנות למחיקה בתיקייה {FOLDER_ID_IMAGES}...")
    img_list_result = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    all_imgs = img_list_result.get('files', [])

    deleted_count = 0
    for img in all_imgs:
        name = img['name']
        # פורמט חדש תקין: מכיל _row_ ואחריו מספר
        if not re.search(r'_row_\d+', name, re.IGNORECASE):
            try:
                service.files().delete(
                    fileId=img['id'],
                    supportsAllDrives=True,
                ).execute()
                print(f"  🗑️  נמחקה תמונה ישנה: {name}")
                deleted_count += 1
            except Exception as e:
                print(f"  ⚠️  לא ניתן למחוק {name}: {e}")

    if deleted_count == 0:
        print("  ✅ לא נמצאו תמונות ישנות — הכל נקי.")
    else:
        print(f"  ✅ נמחקו {deleted_count} תמונות ישנות.")

    # ══════════════════════════════════════════════════════════════════════
    # שלב 2 — בניית רשימת תמונות קיימות בפורמט החדש (כדי לא לשכפל)
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n🔍 סורק תמונות קיימות בפורמט החדש...")
    img_list_result = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents",
        fields="files(name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    existing_imgs = {f['name'].lower() for f in img_list_result.get('files', [])}
    print(f"  📦 {len(existing_imgs)} תמונות קיימות בפורמט החדש.")

    # ══════════════════════════════════════════════════════════════════════
    # שלב 3 — סריקת קבצי אקסל וחילוץ תמונות עם מספר שורה אמיתי
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n🔍 סורק אקסלים בתיקייה {FOLDER_ID_EXCELS}...")
    excels_result = service.files().list(
        q=f"'{FOLDER_ID_EXCELS}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    excels = excels_result.get('files', [])

    if not excels:
        print("⚠️ לא נמצאו קבצי אקסל בתיקייה.")
        return

    for excel in excels:
        file_name = excel['name']
        file_id   = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        print(f"\n--- מעבד: {file_name} ---")

        try:
            # הורדת האקסל לקובץ זמני
            request = service.files().get_media(fileId=file_id)
            ext = file_name.rsplit('.', 1)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                downloader = MediaIoBaseDownload(tmp, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                tmp_excel_path = tmp.name

            workbook = Workbook()
            workbook.LoadFromFile(tmp_excel_path)

            for sheet_idx in range(workbook.Worksheets.Count):
                sheet = workbook.Worksheets[sheet_idx]

                for pic_idx in range(sheet.Pictures.Count):
                    pic = sheet.Pictures[pic_idx]

                    # ── מספר השורה האמיתי של התמונה באקסל ────────────────
                    # TopRow = שורת הפינה הימנית-עליונה של התמונה (0-based)
                    # זה המפתח שמקשר תמונה ↔ מוצר ב-app.py
                    try:
                        row_number = pic.TopRow
                    except AttributeError:
                        try:
                            row_number = pic.Row
                        except AttributeError:
                            row_number = pic_idx
                            print(f"  ⚠️  לא ניתן לקרוא TopRow — משתמש ב-{pic_idx}")

                    # ── שם בפורמט החדש ────────────────────────────────────
                    img_name = f"{base_name}_row_{row_number}.png"

                    if img_name.lower() in existing_imgs:
                        print(f"  ✅ {img_name} כבר קיים — מדלג.")
                        continue

                    # ── שמירה ועלייה לדרייב ───────────────────────────────
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                        tmp_img_path = tmp_img.name

                    pic.Picture.Save(tmp_img_path)

                    media = MediaFileUpload(tmp_img_path, resumable=True)
                    service.files().create(
                        body={'name': img_name, 'parents': [FOLDER_ID_IMAGES]},
                        media_body=media,
                        supportsAllDrives=True,
                    ).execute()

                    print(f"  🚀 הועלה: {img_name}  (sheet={sheet_idx}, row={row_number})")

                    try:
                        os.remove(tmp_img_path)
                    except OSError:
                        pass

            workbook.Dispose()
            os.remove(tmp_excel_path)

        except Exception as e:
            print(f"  ❌ שגיאה ב-{file_name}: {e}")

    print("\n✅ סיום — כל התמונות עודכנו בפורמט החדש.")


if __name__ == "__main__":
    process_excels()
