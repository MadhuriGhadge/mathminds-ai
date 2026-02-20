import streamlit as st
import requests
import json
import base64
from PIL import Image
import io
import os
import uuid
import time
from streamlit_drawable_canvas import st_canvas
from dotenv import load_dotenv

load_dotenv()

# ── Session state: ALL keys initialized ONCE at the very top ─────────────────
# BUG 1 WAS HERE: The original code had TWO `if "user" not in st.session_state`
# blocks — one here and one again at line ~4797 after the CSS/config blocks.
# Streamlit re-runs the whole script top-to-bottom on every rerun. On the rerun
# triggered after login, the second block executed and found "user" ALREADY in
# session_state (because we just set it during login), so it was a no-op —
# BUT on a hard browser refresh the two blocks ran in the same execution pass
# and the second one re-initialized user=None, wiping the login state.
# FIX: One single initialization block here, never again below.
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "user" not in st.session_state:
    st.session_state.user = None
if "current_view" not in st.session_state:
    st.session_state.current_view = "Chat"

# ====================================================
# Page Config — must come before any st.* calls
# ====================================================
st.set_page_config(
    page_title="MathMinds AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================================================
# Premium Global Styling
# ====================================================
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgb(17 24 39) 0%, rgb(10 10 10) 90%);
        font-family: 'Inter', sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    div[data-testid="stChatMessageUser"] {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        border-radius: 20px 20px 4px 20px;
        padding: 1rem 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border: 1px solid rgba(255,255,255,0.1);
    }
    div[data-testid="stChatMessageAssistant"] {
        background: rgba(31, 41, 55, 0.7);
        backdrop-filter: blur(10px);
        border-radius: 20px 20px 20px 4px;
        padding: 1rem 1.5rem;
        border: 1px solid rgba(255,255,255,0.05);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    h1, h2, h3 { color: #f3f4f6; letter-spacing: -0.5px; }
    p, li { color: #e5e7eb; line-height: 1.6; }
    .canvas-container {
        border-radius: 12px; overflow: hidden;
        border: 2px solid rgba(99, 102, 241, 0.3);
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.1);
    }
    .badge {
        display: inline-flex; align-items: center;
        padding: 0.25rem 0.75rem; border-radius: 9999px;
        font-size: 0.75rem; font-weight: 600; margin-right: 0.5rem;
    }
    .badge-blue  { background: rgba(59,130,246,0.2);  color: #93c5fd; border: 1px solid rgba(59,130,246,0.3); }
    .badge-purple{ background: rgba(168,85,247,0.2);  color: #d8b4fe; border: 1px solid rgba(168,85,247,0.3); }
    .badge-green { background: rgba(34,197,94,0.2);   color: #86efac; border: 1px solid rgba(34,197,94,0.3); }
    button[kind="primary"] {
        background: linear-gradient(to right, #4f46e5, #7c3aed);
        border: none; box-shadow: 0 4px 6px -1px rgba(79,70,229,0.3); transition: all 0.2s;
    }
    button[kind="primary"]:hover { transform: translateY(-1px); }
</style>
""", unsafe_allow_html=True)

# ====================================================
# Config & State
# ====================================================
API_URL = "http://localhost:8000/solve"
HISTORY_FILE = "chat_history.json"

if "chat_sessions" not in st.session_state:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            st.session_state.chat_sessions = json.load(f)
    else:
        st.session_state.chat_sessions = {}

if "active_session_id" not in st.session_state:
    sid = str(uuid.uuid4())
    st.session_state.chat_sessions[sid] = {"title": "New Session", "messages": [], "created_at": time.time()}
    st.session_state.active_session_id = sid

# ── IMPORTANT: No second "user" init block here. See top of file. ─────────────

# ====================================================
# Helper Functions
# ====================================================
def save_history():
    with open(HISTORY_FILE, "w") as f:
        json.dump(st.session_state.chat_sessions, f, indent=2)

def get_active_session():
    return st.session_state.chat_sessions[st.session_state.active_session_id]

def add_message(role, content, sent_to_api=False, **kwargs):
    session = get_active_session()
    msg = {"role": role, "content": content, "timestamp": time.time(), "sent_to_api": sent_to_api}
    msg.update(kwargs)
    session["messages"].append(msg)
    save_history()

def new_chat():
    sid = str(uuid.uuid4())
    st.session_state.chat_sessions[sid] = {"title": "New Session", "messages": [], "created_at": time.time()}
    st.session_state.active_session_id = sid
    save_history()
    st.rerun()

def delete_chat(sid):
    if sid in st.session_state.chat_sessions:
        del st.session_state.chat_sessions[sid]
        if st.session_state.active_session_id == sid:
            if st.session_state.chat_sessions:
                st.session_state.active_session_id = list(st.session_state.chat_sessions.keys())[0]
            else:
                new_chat()
        save_history()
        st.rerun()

# ====================================================
# Login Screen
# ====================================================
def login_screen():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.write("")
        st.write("")
        st.markdown("""
        <div style="text-align:center;padding:4rem;background:rgba(255,255,255,0.05);border-radius:20px;border:1px solid rgba(255,255,255,0.1);">
            <h1>🧠 MathMinds AI</h1>
            <p style="color:#9ca3af;">Your intelligent quantitative assistant.</p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

        with tab_login:
            with st.form("login_form"):
                email    = st.text_input("Email", placeholder="student@university.edu")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    if email and password:
                        api_key = os.getenv("FIREBASE_WEB_API_KEY")
                        if not api_key:
                            st.error("Missing FIREBASE_WEB_API_KEY in .env")
                        else:
                            try:
                                url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                                r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=30)
                                if r.status_code == 200:
                                    d = r.json()
                                    st.session_state.user = {"email": d["email"], "token": d["idToken"], "uid": d["localId"]}
                                    st.success(f"Welcome back, {d['email']}!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(f"Login Failed: {r.json().get('error',{}).get('message','Unknown error')}")
                            except Exception as e:
                                st.error(f"Connection Error: {e}")
                    else:
                        st.error("Please enter email and password.")

        with tab_signup:
            with st.form("signup_form"):
                new_email        = st.text_input("New Email", placeholder="new@student.edu")
                new_password     = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if new_email and new_password:
                        if new_password != confirm_password:
                            st.error("Passwords do not match!")
                        else:
                            api_key = os.getenv("FIREBASE_WEB_API_KEY")
                            if not api_key:
                                st.error("Missing FIREBASE_WEB_API_KEY in .env")
                            else:
                                try:
                                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
                                    r = requests.post(url, json={"email": new_email, "password": new_password, "returnSecureToken": True}, timeout=30)
                                    if r.status_code == 200:
                                        d = r.json()
                                        st.session_state.user = {"email": d["email"], "token": d["idToken"], "uid": d["localId"]}
                                        st.success(f"Account Created! Welcome, {d['email']}!")
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(f"Sign Up Failed: {r.json().get('error',{}).get('message','Unknown error')}")
                                except Exception as e:
                                    st.error(f"Connection Error: {e}")
                    else:
                        st.error("Please fill all fields.")

        st.markdown("<p style='text-align:center;font-size:0.8rem;color:#6b7280;'>Powered by Gemini & SymPy</p>", unsafe_allow_html=True)

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not st.session_state.user:
    login_screen()
    st.stop()

# ====================================================
# Profile Interface
# ====================================================
def profile_interface():
    st.title("👤 User Profile")
    st.markdown("Customize your MathMinds experience.")
    headers = {"Authorization": f"Bearer {st.session_state.user['token']}"}

    if "profile_data" not in st.session_state:
        try:
            r = requests.get(f"{API_URL.replace('/solve','')}/users/profile", headers=headers, timeout=30)
            st.session_state.profile_data = r.json() if r.status_code == 200 else {}
        except Exception:
            st.session_state.profile_data = {}

    data = st.session_state.profile_data
    levels = ["High School", "Undergraduate", "Graduate", "Researcher"]
    interests_all = ["Algebra", "Calculus", "Geometry", "Statistics", "Physics", "Computer Science", "Finance"]

    with st.form("profile_form"):
        display_name = st.text_input("Display Name", value=data.get("display_name", ""))
        math_level   = st.selectbox("Math Proficiency Level", levels,
                                    index=levels.index(data.get("math_level","Undergraduate"))
                                    if data.get("math_level") in levels else 1)
        interests    = st.multiselect("Areas of Interest", interests_all,
                                      default=[i for i in data.get("interests",[]) if i in interests_all])
        if st.form_submit_button("Save Profile", use_container_width=True, type="primary"):
            payload = {"display_name": display_name, "math_level": math_level, "interests": interests}
            try:
                r = requests.post(f"{API_URL.replace('/solve','')}/users/profile", json=payload, headers=headers)
                if r.status_code == 200:
                    st.success("Profile updated!")
                    st.session_state.profile_data = payload
                    time.sleep(1); st.rerun()
                else:
                    st.error(f"Update failed: {r.text}")
            except Exception as e:
                st.error(f"Error saving: {e}")

# ====================================================
# Chat Interface
# ====================================================
def chat_interface():
    if st.session_state.active_session_id not in st.session_state.chat_sessions:
        new_chat()

    st.title(st.session_state.chat_sessions[st.session_state.active_session_id]["title"])
    session = get_active_session()

    # ── 1. Render history ─────────────────────────────────────────────────────
    for msg in session["messages"]:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                if msg.get("image_data"):
                    st.image(base64.b64decode(msg["image_data"]), width=300)
                st.write(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                meta = msg.get("metadata", {})
                if meta:
                    badges = ""
                    src = meta.get("source", "")
                    if src == "sympy_preflight":
                        badges += '<span class="badge badge-green">⚡ INSTANT</span>'
                    elif src == "cache":
                        badges += '<span class="badge badge-blue">💾 CACHED</span>'
                    elif src in ("google_adk_agent", "agent"):
                        badges += '<span class="badge badge-purple">🤖 AGENT</span>'
                    model = meta.get("model_used")
                    if model:
                        badges += f'<span class="badge" style="background:rgba(255,255,255,0.1);">{model}</span>'
                    if badges:
                        st.markdown(badges, unsafe_allow_html=True)

                content = msg["content"]
                if msg.get("reasoning"):
                    with st.expander("Show Reasoning Steps"):
                        st.markdown(msg["reasoning"])
                if isinstance(content, dict) and "final_answer" in content:
                    st.markdown(f"**Answer:**\n\n> {content['final_answer']}")
                else:
                    st.markdown(str(content))

    # ── 2. Input area ─────────────────────────────────────────────────────────
    st.divider()
    tab_text, tab_draw, tab_upload = st.tabs(["💬 Text", "✏️ Draw", "📤 Upload"])
    prompt    = None
    image_b64 = None
    is_processing = st.session_state.get("is_processing", False)

    with tab_text:
        prompt = st.chat_input("Ask a math question...", disabled=is_processing)

    with tab_draw:
        col_canvas, col_controls = st.columns([3, 1])
        with col_canvas:
            if "canvas_key" not in st.session_state:
                st.session_state.canvas_key = "main_canvas"
            canvas_result = st_canvas(
                stroke_width=3, stroke_color="#FFFFFF", background_color="#000000",
                height=300, width=600, drawing_mode="freedraw", key=st.session_state.canvas_key,
            )
            draw_prompt = st.text_input("Question about drawing (optional)", placeholder="Solve this handwritten problem...")
        with col_controls:
            st.caption("Controls")
            if st.button("Clear Canvas"):
                st.session_state.canvas_key = f"canvas_{uuid.uuid4()}"
                st.rerun()
            if st.button("Solve Drawing", type="primary", disabled=is_processing):
                if canvas_result.image_data is not None:
                    img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
                    bg  = Image.new("RGB", img.size, (0, 0, 0))
                    bg.paste(img, mask=img.split()[3])
                    buf = io.BytesIO()
                    bg.save(buf, format="PNG")
                    image_b64 = base64.b64encode(buf.getvalue()).decode()
                    prompt = draw_prompt or "Solve this handwritten math problem."

    with tab_upload:
        uploaded     = st.file_uploader("Upload Image", type=["png","jpg"], disabled=is_processing)
        upload_prompt = st.text_input("Question about image (optional)", placeholder="Analyze this image...", disabled=is_processing)
        if uploaded and st.button("Analyze Image", disabled=is_processing):
            image_b64 = base64.b64encode(uploaded.getvalue()).decode()
            prompt    = upload_prompt or "Analyze this image."

    # ── 3. New user message → optimistic write + rerun ────────────────────────
    if prompt:
        req_id = str(uuid.uuid4())
        add_message("user", prompt, image_data=image_b64, request_id=req_id, sent_to_api=False)
        st.session_state.is_processing = True
        st.rerun()

    # ── 4. Recovery: if we restarted mid-flight, allow retry ──────────────────
    if session["messages"] and session["messages"][-1]["role"] == "user":
        last = session["messages"][-1]
        if last.get("sent_to_api") and not st.session_state.is_processing:
            last["sent_to_api"] = False
            save_history()

    # ── 5. Fire API call if last message is unsent user message ───────────────
    if (
        session["messages"]
        and session["messages"][-1]["role"] == "user"
        and not session["messages"][-1].get("sent_to_api", False)
    ):
        last = session["messages"][-1]
        current_request_id = last.get("request_id") or str(uuid.uuid4())
        last["request_id"] = current_request_id

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Agent is thinking..."):
                try:
                    last["sent_to_api"] = True
                    save_history()

                    payload = {
                        "text":             last["content"],
                        "image":            last.get("image_data"),
                        "model_preference": "agent",
                        "session_id":       st.session_state.active_session_id,
                        "request_id":       current_request_id,
                    }
                    headers = {}
                    if st.session_state.user:
                        headers["Authorization"] = f"Bearer {st.session_state.user['token']}"

                    response = requests.post(API_URL, json=payload, headers=headers, timeout=360)

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success":
                            answer_raw = data.get("answer") or data.get("explanation") or "⚠️ No answer returned."
                            meta       = data.get("metadata", {})
                            add_message(
                                "assistant",
                                answer_raw,
                                reasoning=data.get("explanation"),
                                metadata={
                                    "source":     data.get("source", "agent"),
                                    "model_used": meta.get("model", "gemini-2.5-flash"),
                                    "latency":    f"{meta.get('latency_ms',0)/1000:.2f}s",
                                    "tools":      meta.get("tools_used", []),
                                },
                                steps=data.get("steps", [])
                            )
                            st.session_state.is_processing = False
                            st.rerun()   # ← BUG 2 FIX: missing rerun caused blank UI

                        else:
                            error_msg = data.get("error", "Unknown error")
                            add_message("assistant", f"⚠️ Error: {error_msg}")
                            st.session_state.is_processing = False
                            st.rerun()

                    elif response.status_code in [202, 409]:
                        st.info("ℹ️ Request already processing.")
                        st.session_state.is_processing = False
                        st.rerun()

                    else:
                        try:
                            err_msg = response.json().get("error", f"HTTP {response.status_code}")
                        except Exception:
                            err_msg = f"HTTP {response.status_code}"
                        add_message("assistant", f"❌ Server Error: {err_msg}")
                        st.session_state.is_processing = False
                        st.rerun()

                except Exception as e:
                    add_message("assistant", f"❌ Connection Failed: {str(e)}")
                    st.session_state.is_processing = False
                    st.rerun()

# ====================================================
# Sidebar
# ====================================================
with st.sidebar:
    st.markdown("### 🧠 MathMinds")
    st.write(f"Logged in as **{st.session_state.user['email']}**")

    view = st.radio("Navigation", ["Chat", "Profile"],
                    index=0 if st.session_state.current_view == "Chat" else 1)
    if view != st.session_state.current_view:
        st.session_state.current_view = view
        st.rerun()

    if st.button("Sign Out", type="secondary"):
        st.session_state.user = None
        st.rerun()

    st.divider()

    if st.session_state.current_view == "Chat":
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            new_chat()

        st.markdown("#### History")
        sorted_sids = sorted(
            st.session_state.chat_sessions.keys(),
            key=lambda k: st.session_state.chat_sessions[k].get("created_at", 0),
            reverse=True
        )
        for sid in sorted_sids:
            sess    = st.session_state.chat_sessions[sid]
            title   = sess.get("title", "Untitled")
            isActive = (sid == st.session_state.active_session_id)
            col_nav, col_del = st.columns([0.85, 0.15])
            with col_nav:
                if st.button(f"{'📍 ' if isActive else ''}{title}", key=sid, use_container_width=True):
                    st.session_state.active_session_id = sid
                    st.rerun()
            with col_del:
                if isActive and st.button("🗑️", key=f"del_{sid}"):
                    delete_chat(sid)

# ── Router ────────────────────────────────────────────────────────────────────
if st.session_state.current_view == "Profile":
    profile_interface()
else:
    chat_interface()