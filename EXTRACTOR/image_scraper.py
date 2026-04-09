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

# מספר שורות ריקות רצופות שמסמנות גבול בין מוצרים
EMPTY_ROWS_THRESHOLD = 1


def get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    encoded_key = constants.GCP_SERVICE_ACCOUNT
    decoded_key = base64.b64decode(encoded_key).decode('utf-8')
    info = json.loads(decoded_key)
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)


def is_row_empty(sheet, row_idx):
    """בודק אם שורה מסוימת ריקה לחלוטין."""
    try:
        for col_idx in range(sheet.Columns.Count):
            cell = sheet.Range[row_idx + 1, col_idx + 1]  # Spire is 1-based
            if cell.Value and str(cell.Value).strip():
                return False
        return True
    except Exception:
        return True


def find_product_blocks(sheet):
    """
    מזהה בלוקי מוצרים לפי שורות ריקות.
    מחזיר רשימה של (start_row, end_row) — 0-based.
    """
    total_rows = sheet.Rows.Count
    blocks = []
    in_block = False
    block_start = 0
    consecutive_empty = 0

    for r in range(total_rows):
        empty = is_row_empty(sheet, r)
        if not empty:
            if not in_block:
                in_block = True
                block_start = r
            consecutive_empty = 0
        else:
            if in_block:
                consecutive_empty += 1
                if consecutive_empty >= EMPTY_ROWS_THRESHOLD:
                    # סוף בלוק
                    blocks.append((block_start, r - consecutive_empty + 1))
                    in_block = False
                    consecutive_empty = 0

    # בלוק אחרון אם הגיע לסוף הגיליון
    if in_block:
        blocks.append((block_start, total_rows - 1))

    return blocks


def process_excels():
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    from spire.xls import Workbook

    service = get_service()
    if not service:
        return

    # ══════════════════════════════════════════════════════════════════════
    # שלב 1 — מחיקת תמונות ישנות (ללא _row_ בשם)
    # ══════════════════════════════════════════════════════════════════════
    print(f"🔍 בודק תמונות ישנות למחיקה...")
    img_list = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute().get('files', [])

    deleted = 0
    for img in img_list:
        if not re.search(r'_row_\d+', img['name'], re.IGNORECASE):
            try:
                service.files().delete(
                    fileId=img['id'], supportsAllDrives=True
                ).execute()
                print(f"  🗑️  נמחקה: {img['name']}")
                deleted += 1
            except Exception as e:
                print(f"  ⚠️  לא ניתן למחוק {img['name']}: {e}")
    print(f"  ✅ נמחקו {deleted} תמונות ישנות." if deleted else "  ✅ אין תמונות ישנות.")

    # ══════════════════════════════════════════════════════════════════════
    # שלב 2 — תמונות קיימות בפורמט החדש
    # ══════════════════════════════════════════════════════════════════════
    existing_imgs = {
        f['name'].lower()
        for f in service.files().list(
            q=f"'{FOLDER_ID_IMAGES}' in parents",
            fields="files(name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute().get('files', [])
    }
    print(f"📦 {len(existing_imgs)} תמונות קיימות בפורמט החדש.")

    # ══════════════════════════════════════════════════════════════════════
    # שלב 3 — סריקת אקסלים
    # ══════════════════════════════════════════════════════════════════════
    excels = service.files().list(
        q=f"'{FOLDER_ID_EXCELS}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute().get('files', [])

    if not excels:
        print("⚠️ לא נמצאו קבצי אקסל.")
        return

    for excel in excels:
        file_name = excel['name']
        file_id   = excel['id']
        base_name = file_name.rsplit('.', 1)[0]
        print(f"\n--- מעבד: {file_name} ---")

        try:
            # הורדה
            ext = file_name.rsplit('.', 1)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                downloader = MediaIoBaseDownload(
                    tmp, service.files().get_media(fileId=file_id)
                )
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                tmp_excel_path = tmp.name

            workbook = Workbook()
            workbook.LoadFromFile(tmp_excel_path)

            for sheet_idx in range(workbook.Worksheets.Count):
                sheet = workbook.Worksheets[sheet_idx]
                print(f"  📄 גיליון {sheet_idx}: {sheet.Pictures.Count} תמונות")

                if sheet.Pictures.Count == 0:
                    continue

                # ── בניית מיפוי: TopRow → רשימת תמונות ──────────────────
                # כל תמונה ממוינת לפי שורת ה-top שלה
                pics_by_row = {}
                for pic_idx in range(sheet.Pictures.Count):
                    pic = sheet.Pictures[pic_idx]
                    try:
                        top_row = pic.TopRow
                    except AttributeError:
                        try:
                            top_row = pic.Row
                        except AttributeError:
                            top_row = pic_idx
                    pics_by_row.setdefault(top_row, []).append(pic)

                # ── זיהוי בלוקי מוצרים ───────────────────────────────────
                blocks = find_product_blocks(sheet)
                print(f"  📦 נמצאו {len(blocks)} בלוקי מוצרים")

                for block_start, block_end in blocks:
                    # כל תמונה שה-TopRow שלה נמצא בתוך הבלוק
                    block_pics = []
                    for top_row, pics in sorted(pics_by_row.items()):
                        if block_start <= top_row <= block_end:
                            block_pics.extend(pics)

                    if not block_pics:
                        continue

                    # שמירה: base_row_<block_start>_img_<N>.png
                    for img_idx, pic in enumerate(block_pics):
                        img_name = f"{base_name}_row_{block_start}_img_{img_idx}.png"

                        if img_name.lower() in existing_imgs:
                            print(f"    ✅ {img_name} קיים — מדלג.")
                            continue

                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".png"
                        ) as tmp_img:
                            tmp_img_path = tmp_img.name

                        try:
                            pic.Picture.Save(tmp_img_path)
                            media = MediaFileUpload(tmp_img_path, resumable=True)
                            service.files().create(
                                body={
                                    'name': img_name,
                                    'parents': [FOLDER_ID_IMAGES],
                                },
                                media_body=media,
                                supportsAllDrives=True,
                            ).execute()
                            print(f"    🚀 הועלה: {img_name}")
                        except Exception as e:
                            print(f"    ❌ שגיאה בתמונה {img_name}: {e}")
                        finally:
                            try:
                                os.remove(tmp_img_path)
                            except OSError:
                                pass

            workbook.Dispose()
            os.remove(tmp_excel_path)

        except Exception as e:
            print(f"  ❌ שגיאה ב-{file_name}: {e}")

    print("\n✅ סיום — כל התמונות עודכנו.")


if __name__ == "__main__":
    process_excels()
