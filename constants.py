# constants.py
# ⚠️ מפתח השירות לא נשמר כאן. הוא נטען בזמן ריצה משני מקורות מאובטחים:
#   1) Streamlit Secrets  (שם המפתח: GCP_SERVICE_ACCOUNT) — באפליקציה
#   2) משתנה סביבה GCP_SERVICE_ACCOUNT — ברובוט ב-GitHub Actions
# הערך יכול להיות או ה-JSON הגולמי של המפתח, או JSON מקודד ב-Base64 — שניהם נתמכים.

import os
import json
import base64


def _read_raw():
    try:
        import streamlit as st
        v = st.secrets.get("GCP_SERVICE_ACCOUNT", None)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get("GCP_SERVICE_ACCOUNT", "")


def get_service_account_info():
    """מחזיר את פרטי חשבון השירות (dict), או None אם לא הוגדר."""
    raw = (_read_raw() or "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        return json.loads(raw)
    return json.loads(base64.b64decode(raw).decode("utf-8"))


# תאימות לאחור (אם קוד ישן עדיין משתמש בשם הזה)
GCP_SERVICE_ACCOUNT = _read_raw()
