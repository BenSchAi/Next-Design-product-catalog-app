import streamlit as st
import time

# 1. הגדרות עמוד (חובה שיופיעו ראשונות)
st.set_page_config(
    page_title="NEXT DESIGN | Premium Access", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# 2. יצירת מיכל ריק שיכיל את כל דף הכניסה
placeholder = st.empty()

# 3. פונקציה שמציגה את כל מסך הכניסה המעוצב
def show_login_page():
    with placeholder.container():
        # הזרקת ה-CSS היוקרתי (זהב, נצנוצים ואנימציות)
        st.markdown("""
            <style>
            .stApp { background-color: #000000; color: #FFFFFF; overflow: hidden; }
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {background-color: transparent !important;}
            
            @keyframes moveStars { from { transform: translateY(0px); } to { transform: translateY(-2000px); } }
            .stars-background {
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1;
                background: transparent url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAANElEQVRoQ+3OsQkAAAgDMMP/T65fOIFwU5A6Z2bMvM0+3j55555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555k=') repeat top center;
                opacity: 0.3; animation: moveStars 100s linear infinite;
            }
            
            @keyframes goldShimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
            .gold-logo-text {
                font-family: 'Montserrat', sans-serif; font-weight: 900; letter-spacing: 4px; font-size: 80px !important;
                background: linear-gradient(to right, #BF9B30 0%, #F7EF8A 25%, #FFFFFF 50%, #F7EF8A 75%, #BF9B30 100%);
                background-size: 200% auto; color: transparent; -webkit-background-clip: text; background-clip: text;
                animation: goldShimmer 4s linear infinite; display: block; text-align: center; margin-top: 100px;
            }
            
            .premium-subtitle {
                text-align: center; font-family: 'Montserrat', sans-serif; color: #888888;
                font-weight: 300; font-size: 22px; letter-spacing: 2px; margin-top: 10px; margin-bottom: 50px;
            }

            div[data-testid="stTextInput"] > div > div > input {
                border-radius: 0px !important; border: 1px solid #444 !important;
                background-color: #111 !important; color: #F7EF8A !important;
                font-size: 20px !important; text-align: center;
            }
            div[data-testid="stTextInput"] > div > div > input:focus {
                border-color: #F7EF8A !important;
                box-shadow: 0 0 15px rgba(247, 239, 138, 0.3) !important;
            }
            
            /* --- התוספת החדשה: עיצוב כפתור הכניסה --- */
            div[data-testid="stButton"] > button {
                background-color: #BF9B30 !important;
                color: #000 !important;
                font-weight: bold !important;
                border-radius: 5px !important;
                border: none !important;
                font-size: 18px !important;
                margin-top: 15px !important;
            }
            div[data-testid="stButton"] > button:hover {
                background-color: #F7EF8A !important;
                color: #000 !important;
            }
            </style>
            
            <div class="stars-background"></div>
            <span class="gold-logo-text">NEXT DESIGN</span>
            <p class="premium-subtitle">PREMIUM ACCESS | SMART CATALOG</p>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<p style="text-align:center; color:#AAA; font-size:16px;">אנא הכנס את קוד הגישה האישי שלך:</p>', unsafe_allow_html=True)
            
            # --- התיקון: הוספנו autocomplete="current-password" כדי לעצור את ההצעה של גוגל ---
            code_val = st.text_input("", type="password", placeholder="CODE", key="main_login_input", autocomplete="current-password")
            
            # --- התיקון: כפתור ברור במקום להסתמך רק על אנטר ---
            st.button("היכנס לקטלוג 🔑", use_container_width=True)
            
            return code_val

# 4. הרצת הלוגיקה של הכניסה
user_code = show_login_page()

if user_code == "1234":
    # מחיקת מסך הכניסה
    placeholder.empty()
    
    # מיכל זמני להודעת מעבר
    transition_container = st.empty()
    with transition_container.container():
        st.markdown('<p style="text-align:center; color:#F7EF8A; font-size:22px; margin-top:200px;">מעביר אותך לקטלוג המקצועי...</p>', unsafe_allow_html=True)
        time.sleep(1.2)
    
    # מחיקת הודעת המעבר כדי שהדף יהיה נקי לגמרי
    transition_container.empty()
    
    # טעינת הקטלוג המקורי מתוך app.py
    try:
        with open("app.py", encoding="utf-8") as f:
            code = f.read()
            exec(code, globals())
    except Exception as e:
        st.error(f"שגיאה בטעינת הקטלוג: {e}")
