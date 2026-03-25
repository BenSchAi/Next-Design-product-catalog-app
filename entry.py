import streamlit as st
import time

# הגדרות עמוד בסיסיות למסך הכניסה
st.set_page_config(
    page_title="NEXT DESIGN | Premium Access", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# 1. הזרקת ה"קסם" של העיצוב (CSS)
# כאן אנחנו מגדירים את הזהב המנצנץ, הרקע השחור עם הנצנוצים, והאנימציות
st.markdown("""
    <style>
    /* הגדרות כלליות לדף הכניסה */
    .stApp {
        background-color: #000000; /* רקע שחור עמוק */
        color: #FFFFFF; /* טקסט לבן */
        overflow: hidden; /* מניעת סרגלי גלילה בגלל הנצנוצים */
    }
    
    /* הסתרת תפריטים מיותרים */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background-color: transparent !important;}
    
    /* --- אפקט נצנוצים (כוכבים) ברקע --- */
    @keyframes moveStars {
        from { transform: translateY(0px); }
        to { transform: translateY(-2000px); }
    }
    
    /* שכבת הנצנוצים */
    .stars-background {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: -1; /* מאחורי הכל */
        background: transparent url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAANElEQVRoQ+3OsQkAAAgDMMP/T65fOIFwU5A6Z2bMvM0+3j55555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555555k=') repeat top center;
        opacity: 0.3; /* עדינות */
        animation: moveStars 100s linear infinite; /* תנועה אטית ומחזורית */
    }
    
    /* --- עיצוב הלוגו הדינאמי - זהב מנצנץ (Shimmer) --- */
    @keyframes goldShimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    .gold-logo-text {
        font-family: 'Montserrat', sans-serif; /* פונט יוקרתי */
        font-weight: 900;
        letter-spacing: 4px;
        font-size: 80px !important;
        
        /* אפקט הזהב */
        background: linear-gradient(
            to right, 
            #BF9B30 0%, /* זהב ברונזה */
            #F7EF8A 25%, /* זהב בהיר */
            #FFFFFF 50%, /* לבן לנצנוץ */
            #F7EF8A 75%, /* זהב בהיר */
            #BF9B30 100% /* זהב ברונזה */
        );
        background-size: 200% auto;
        color: transparent;
        -webkit-background-clip: text;
        background-clip: text;
        
        /* האנימציה המנצנצת של הלוגו */
        animation: goldShimmer 4s linear infinite;
        
        display: block;
        text-align: center;
        margin-bottom: -10px;
    }
    
    /* עיצוב כותרת המשנה */
    .premium-subtitle {
        text-align: center;
        font-family: 'Montserrat', sans-serif;
        color: #888888;
        font-weight: 300;
        font-size: 22px;
        letter-spacing: 2px;
        margin-top: 10px;
        margin-bottom: 50px;
    }
    
    /* עיצוב שדה הקלט */
    div[data-testid="stTextInput"] > div > div > input {
        border-radius: 0px !important;
        border: 1px solid #444 !important;
        background-color: #111 !important;
        color: #F7EF8A !important; /* טקסט קלט בזהב */
        font-size: 20px !important;
        text-align: center;
    }
    div[data-testid="stTextInput"] > div > div > input:focus {
        border-color: #F7EF8A !important;
        box-shadow: 0 0 15px rgba(247, 239, 138, 0.3) !important;
    }
    
    /* עיצוב כפתור הכניסה */
    .stButton > button {
        background: linear-gradient(45deg, #BF9B30, #F7EF8A, #BF9B30) !important;
        color: #000 !important;
        font-weight: 900 !important;
        letter-spacing: 2px !important;
        border: none !important;
        border-radius: 0px !important;
        font-family: 'Montserrat', sans-serif;
        font-size: 18px !important;
        text-transform: uppercase;
        padding: 15px 30px !important;
        transition: all 0.3s ease !important;
    }
    .stButton > button:hover {
        box-shadow: 0 0 25px rgba(247, 239, 138, 0.6) !important;
        transform: translateY(-2px);
    }
    
    </style>
""", unsafe_allow_html=True)

# 2. הוספת שכבת הנצנוצים (הכוכבים הנעים) ברקע
st.markdown('<div class="stars-background"></div>', unsafe_allow_html=True)

# 3. הצגת האלמנטים המעוצבים
# הלוגו המנצנץ
st.markdown('<span class="gold-logo-text">NEXT DESIGN</span>', unsafe_allow_html=True)

# כותרת המשנה היוקרתית
st.markdown('<p class="premium-subtitle">PREMIUM ACCESS | SMART CATALOG</p>', unsafe_allow_html=True)

# 4. אזור האימות
# אנחנו משתמשים בעמודות כדי למרכז את שדה הקלט
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown('<p style="text-align:center; color:#AAA; font-size:16px;">אנא הכנס את קוד הגישה האישי שלך:</p>', unsafe_allow_html=True)
    user_answer = st.text_input("", type="password", placeholder="CODE")
    
    if user_answer:
        if user_answer == "1234": # שנה כאן לקוד שאתה רוצה
            # הודעת הצלחה מעוצבת
            st.markdown('<p style="text-align:center; color:#F7EF8A; font-size:18px;">✅ קוד תקין. גישה מאושרת.</p>', unsafe_allow_html=True)
            
            # אפקט קטן של "טעינה" יוקרתי
            with st.spinner('מעביר אותך לקטלוג...'):
                time.sleep(1.5)
            
            # --- הקסם שקורה כאן (לא לגעת ב-app.py!): ---
            with open("app.py", encoding="utf-8") as f:
                code = f.read()
                exec(code, globals())
                
        else:
            # הודעת שגיאה מעוצבת
            st.markdown('<p style="text-align:center; color:#FF4444; font-size:18px;">❌ קוד שגוי. הגישה חסומה.</p>', unsafe_allow_html=True)
