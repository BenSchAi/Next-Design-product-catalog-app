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

# תמונות שה-LeftColumn שלהן גבוה מזה — נחשבות "מחוץ לריבוע" ומדולגות
MAX_LEFT_COLUMN = 5


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
    # שלב 1 — מחיקת תמונות ישנות (פורמט _N ללא _row_)
    # ══════════════════════════════════════════════════════════════════════
    print("🔍 בודק תמונות ישנות למחיקה...")
    all_imgs = service.files().list(
        q=f"'{FOLDER_ID_IMAGES}' in parents",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute().get('files', [])

    deleted = 0
    for img in all_imgs:
        name = img['name']
        # פורמט ישן: מסתיים ב _N.png (ספרה בלבד, ללא _row_)
        if re.search(r'_\d+\.png$', name, re.IGNORECASE) and '_row_' not in name.lower():
            try:
                service.files().delete(
                    fileId=img['id'], supportsAllDrives=True
                ).execute()
                print(f"  🗑️  נמחקה: {name}")
                deleted += 1
            except Exception as e:
                print(f"  ⚠️  לא ניתן למחוק {name}: {e}")
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
                total_pics = sheet.Pictures.Count
                print(f"  📄 גיליון {sheet_idx}: {total_pics} תמונות")

                if total_pics == 0:
                    continue

                # ── סינון תמונות: רק אלה שבצד שמאל (בתוך הריבוע) ─────────
                # ממיינות לפי TopRow כדי לשמור סדר עקבי
                left_pics = []
                for pic_idx in range(total_pics):
                    pic = sheet.Pictures[pic_idx]
                    try:
                        left_col = pic.LeftColumn
                    except AttributeError:
                        try:
                            left_col = pic.Column
                        except AttributeError:
                            left_col = 0

                    if left_col <= MAX_LEFT_COLUMN:
                        try:
                            top_row = pic.TopRow
                        except AttributeError:
                            try:
                                top_row = pic.Row
                            except AttributeError:
                                top_row = pic_idx
                        left_pics.append((top_row, pic_idx, pic))
                    else:
                        print(f"  ⏭️  דולגה תמונה חיצונית (col={left_col})")

                # מיון לפי שורה
                left_pics.sort(key=lambda x: x[0])

                # ── קיבוץ תמונות לפי מוצר (TopRow קרוב = אותו מוצר) ──────
                # תמונות שה-TopRow שלהן בטווח של MAX_ROW_GAP שורות זו מזו
                # = שייכות לאותו מוצר
                MAX_ROW_GAP = 20
                groups = []   # כל group = (first_top_row, [pics])

                for top_row, pic_idx, pic in left_pics:
                    if not groups or top_row - groups[-1][0] > MAX_ROW_GAP:
                        groups.append((top_row, [pic]))
                    else:
                        groups[-1][1].append(pic)

                print(f"  📦 {len(groups)} קבוצות מוצרים זוהו")

                # ── שמירה: base_row_<first_top_row>_img_<N>.png ───────────
                for first_top_row, pics in groups:
                    for img_idx, pic in enumerate(pics):
                        img_name = f"{base_name}_row_{first_top_row}_img_{img_idx}.png"

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
                            print(f"    🚀 הועלה: {img_name}  (row={first_top_row}, img={img_idx})")
                        except Exception as e:
                            print(f"    ❌ שגיאה: {img_name}: {e}")
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
