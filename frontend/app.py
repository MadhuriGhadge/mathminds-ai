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
from firebase_utils import sign_in_with_email, sign_up_with_email

load_dotenv()

# ── Session state: ALL keys initialized ONCE at the very top ─────────────────
# CRITICAL: These must be the very first st.session_state accesses, before any
# st.* UI calls. Streamlit re-runs the entire script on every interaction.
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "user" not in st.session_state:
    st.session_state.user = None          # None = logged out
if "current_view" not in st.session_state:
    st.session_state.current_view = "Chat"

# MULTIUSER FIX ─ these three keys must be RESET on logout.
# They are initialized here so first-run doesn't KeyError.
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = []
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# MULTIUSER FIX ─ track WHICH user's data is currently loaded.
# If this doesn't match st.session_state.user["uid"], we know we need to reload.
if "loaded_for_user" not in st.session_state:
    st.session_state.loaded_for_user = None

if "renaming_session_id" not in st.session_state:
    st.session_state.renaming_session_id = None

if "canvas_key" not in st.session_state:
    st.session_state.canvas_key = "main_canvas"

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
# Config
# ====================================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_URL = f"{BACKEND_URL}/solve"


# ====================================================
# MULTIUSER ISOLATION — Core helper
# ====================================================
def _clear_user_state():
    """
    Wipe ALL per-user data from Streamlit session state.

    Called on logout and whenever a different user logs in.

    WHY THIS IS THE MOST IMPORTANT FUNCTION FOR MULTIUSER ISOLATION:
    Streamlit's st.session_state is per browser-tab, not per user. If User A
    logs in, chats, then User B logs in on the same tab, all of User A's
    chat_sessions and messages are still sitting in st.session_state. The
    backend correctly refuses to serve User A's data to User B (every DB query
    filters by user_id), but the frontend would still DISPLAY User A's messages
    briefly until the next API call returns. This function prevents that.
    """
    st.session_state.chat_sessions       = []
    st.session_state.active_session_id   = None
    st.session_state.messages            = []
    st.session_state.loaded_for_user     = None
    st.session_state.is_processing       = False
    st.session_state.current_view        = "Chat"
    st.session_state.renaming_session_id = None
    st.session_state.canvas_key          = f"canvas_{uuid.uuid4()}"
    # Also clear profile cache if it exists
    if "profile_data" in st.session_state:
        del st.session_state["profile_data"]


# ====================================================
# Helper Functions
# ====================================================
def get_auth_headers():
    if st.session_state.user and "token" in st.session_state.user:
        return {"Authorization": f"Bearer {st.session_state.user['token']}"}
    return {}


def load_sessions():
    """Fetch THIS user's chat sessions from the backend and populate state."""
    try:
        headers = get_auth_headers()
        try:
            response = requests.get(f"{BACKEND_URL}/chat/sessions", headers=headers, timeout=10)
        except requests.exceptions.ConnectionError:
            st.info("⌛ **MathMinds API is warming up...** Please wait a few seconds.")
            st.stop()
        
        if response.status_code == 200:
            st.session_state.chat_sessions = response.json()
            # Mark that we've successfully loaded data for this specific user
            if st.session_state.user:
                st.session_state.loaded_for_user = st.session_state.user["uid"]
            # Auto-select first session if none active
            if not st.session_state.active_session_id and st.session_state.chat_sessions:
                st.session_state.active_session_id = st.session_state.chat_sessions[0]["session_id"]
                load_messages(st.session_state.active_session_id)
            elif st.session_state.active_session_id and not any(
                s["session_id"] == st.session_state.active_session_id
                for s in st.session_state.chat_sessions
            ):
                # Active session was deleted — pick first or clear
                if st.session_state.chat_sessions:
                    st.session_state.active_session_id = st.session_state.chat_sessions[0]["session_id"]
                    load_messages(st.session_state.active_session_id)
                else:
                    st.session_state.active_session_id = None
                    st.session_state.messages = []
        elif response.status_code == 401:
            # JWT expired — force re-login
            _clear_user_state()
            st.session_state.user = None
            st.error("Session expired. Please log in again.")
        else:
            st.error(f"Failed to load sessions: {response.status_code}")
            st.session_state.chat_sessions = []
    except Exception as e:
        st.error(f"Error loading sessions: {e}")
        st.session_state.chat_sessions = []


def load_messages(session_id):
    """
    Load messages for a session.
    The backend enforces user ownership — it will 404 if session_id
    doesn't belong to the authenticated user, so this is safe.
    """
    try:
        headers = get_auth_headers()
        response = requests.get(
            f"{BACKEND_URL}/chat/sessions/{session_id}/messages",
            headers=headers, timeout=30
        )
        if response.status_code == 200:
            server_messages = response.json()
            local_messages = st.session_state.get("messages", [])

            # ✅ INDESTRUCTIBLE MERGE LOGIC
            # 1. Start with server messages as the definitive baseline.
            merged = []
            server_keys = set()
            for m in server_messages:
                merged.append(m)
                rid = m.get("request_id")
                role = m.get("role")
                if rid and role:
                    server_keys.add((role, rid))

            # 2. Append local messages that have NOT yet reached the server.
            # This protects local "optimistic" messages from vanishing if DB is slow.
            for lm in local_messages:
                rid = lm.get("request_id")
                role = lm.get("role")
                if rid and role:
                    if (role, rid) not in server_keys:
                        merged.append(lm)
                elif not rid:
                    # Fallback for messages without IDs (should be rare)
                    content_prefix = str(lm.get("content", ""))[:50]
                    if not any(str(sm.get("content", "")).startswith(content_prefix) for sm in server_messages):
                        merged.append(lm)

            st.session_state.messages = merged
        elif response.status_code == 404:
            # Session doesn't belong to this user — clear silently
            st.session_state.messages = []
            st.session_state.active_session_id = None
            st.warning("Session not found.")
        else:
            st.session_state.messages = []
            st.error(f"Failed to load messages: {response.status_code}")
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
        st.error(f"Error loading messages: {e}")
        st.session_state.messages = []


def get_active_session():
    for s in st.session_state.chat_sessions:
        if s["session_id"] == st.session_state.active_session_id:
            return s
    return None


def add_message(role, content, sent_to_api=False, request_id=None, **kwargs):
    """Optimistic UI update only — persistence happens in the backend via /solve."""
    msg = {
        "role": role, 
        "content": content, 
        "timestamp": time.time(), 
        "sent_to_api": sent_to_api,
        "request_id": request_id
    }
    msg.update(kwargs)
    st.session_state.messages.append(msg)


def new_chat():
    try:
        headers = get_auth_headers()
        response = requests.post(f"{BACKEND_URL}/chat/sessions", headers=headers, timeout=30)
        if response.status_code == 200:
            new_s = response.json()
            st.session_state.active_session_id = new_s["session_id"]
            st.session_state.messages = []
            load_sessions()
            st.rerun()
        else:
            st.error("Failed to create new chat")
    except Exception as e:
        st.error(f"Error: {e}")


def delete_chat(sid):
    try:
        headers = get_auth_headers()
        response = requests.delete(f"{BACKEND_URL}/chat/sessions/{sid}", headers=headers, timeout=30)
        if response.status_code == 200:
            if st.session_state.active_session_id == sid:
                st.session_state.active_session_id = None
                st.session_state.messages = []
            load_sessions()
            st.rerun()
        else:
            st.error("Failed to delete chat")
    except Exception as e:
        st.error(f"Error: {e}")


def rename_chat(sid, new_title):
    try:
        headers = get_auth_headers()
        response = requests.patch(
            f"{BACKEND_URL}/chat/sessions/{sid}",
            headers=headers, json={"title": new_title}, timeout=30
        )
        if response.status_code == 200:
            load_sessions()
            st.rerun()
        else:
            st.error("Failed to rename chat")
    except Exception as e:
        st.error(f"Error: {e}")


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
                        try:
                            token, uid, user_email, error = sign_in_with_email(email, password)
                            if token:
                                # ✅ MULTIUSER FIX: Clear ALL previous user data
                                _clear_user_state()
                                st.session_state.user = {
                                    "email": user_email,
                                    "token": token,
                                    "uid":   uid
                                }
                                st.success(f"Welcome back, {user_email}!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"Login Failed: {error}")
                        except Exception as e:
                            st.error(f"Connection Error: {e}")
                    else:
                        st.error("Please enter email and password.")

        with tab_signup:
            with st.form("signup_form"):
                new_email        = st.text_input("New Email", placeholder="new@student.edu")
                new_password     = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                full_name        = st.text_input("Full Name", placeholder="Optional")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if new_email and new_password:
                        if new_password != confirm_password:
                            st.error("Passwords do not match!")
                        else:
                            try:
                                token, uid, user_email, error = sign_up_with_email(new_email, new_password)
                                if token:
                                    # ✅ MULTIUSER FIX: Same as login — clear first
                                    _clear_user_state()
                                    st.session_state.user = {
                                        "email": user_email,
                                        "token": token,
                                        "uid":   uid
                                    }
                                    st.success(f"Account Created! Welcome, {user_email}!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(f"Sign Up Failed: {error}")
                            except Exception as e:
                                st.error(f"Connection Error: {e}")
                    else:
                        st.error("Please fill all fields.")

        st.markdown(
            "<p style='text-align:center;font-size:0.8rem;color:#6b7280;'>Powered by Gemini & SymPy</p>",
            unsafe_allow_html=True
        )


# ── Auth gate ─────────────────────────────────────────────────────────────────
if not st.session_state.user:
    login_screen()
    st.stop()

# ====================================================
# ✅ MULTIUSER FIX — Per-rerun data isolation check
# ====================================================
# At this point we know a user IS logged in.
# Check: is the data currently in state actually for THIS user?
# This handles the scenario where User A's browser tab is reused by User B
# (e.g. token swap, shared kiosk, etc.) without a full page reload.
_current_uid = st.session_state.user["uid"]
if st.session_state.loaded_for_user != _current_uid:
    # Data in state belongs to a different user (or nobody) — reload for current user
    _clear_user_state()
    load_sessions()
    # loaded_for_user is set inside load_sessions() on success


# ====================================================
# Profile Interface
# ====================================================
def profile_interface():
    st.title("👤 User Profile")
    st.markdown("Customize your MathMinds experience.")
    headers = get_auth_headers()

    if "profile_data" not in st.session_state:
        try:
            r = requests.get(f"{BACKEND_URL}/users/profile", headers=headers, timeout=30)
            st.session_state.profile_data = r.json() if r.status_code == 200 else {}
        except Exception:
            st.session_state.profile_data = {}

    data = st.session_state.profile_data
    levels = ["High School", "Undergraduate", "Graduate", "Researcher"]
    interests_all = ["Algebra", "Calculus", "Geometry", "Statistics", "Physics", "Computer Science", "Finance"]

    with st.form("profile_form"):
        display_name = st.text_input("Display Name", value=data.get("display_name", ""))
        math_level   = st.selectbox(
            "Math Proficiency Level", levels,
            index=levels.index(data.get("math_level", "Undergraduate"))
            if data.get("math_level") in levels else 1
        )
        interests = st.multiselect(
            "Areas of Interest", interests_all,
            default=[i for i in data.get("interests", []) if i in interests_all]
        )
        if st.form_submit_button("Save Profile", use_container_width=True, type="primary"):
            payload = {"display_name": display_name, "math_level": math_level, "interests": interests}
            try:
                r = requests.post(f"{BACKEND_URL}/users/profile", json=payload, headers=headers)
                if r.status_code == 200:
                    st.success("Profile updated!")
                    st.session_state.profile_data = payload
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Update failed: {r.text}")
            except Exception as e:
                st.error(f"Error saving: {e}")


# ====================================================
# Chat Interface
# ====================================================
def chat_interface():
    if not st.session_state.active_session_id:
        if st.session_state.chat_sessions:
            st.session_state.active_session_id = st.session_state.chat_sessions[0]["session_id"]
            load_messages(st.session_state.active_session_id)
        else:
            new_chat()
            return

    active_sess = get_active_session()
    st.title(active_sess["title"] if active_sess else "Chat")

    # ✅ SELF-HEALING: Reset processing lock if assistant has already replied
    if st.session_state.is_processing and st.session_state.messages:
        if st.session_state.messages[-1]["role"] == "assistant":
             st.session_state.is_processing = False
             # No rerun needed here, just continue to render

    # ── 1. Render history ─────────────────────────────────────────────────────
    for msg in st.session_state.messages:
        role = msg["role"]
        with st.chat_message(role, avatar="👤" if role == "user" else "🤖"):
            if role == "user":
                if msg.get("image_data"):
                    try:
                        st.image(base64.b64decode(msg["image_data"]), width=300)
                    except Exception:
                        pass
                st.write(msg["content"])
            else:
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
                    model = meta.get("model_used") or meta.get("model")
                    if model:
                        badges += f'<span class="badge" style="background:rgba(255,255,255,0.1);">{model}</span>'
                    if badges:
                        st.markdown(badges, unsafe_allow_html=True)

                # Reasoning display removed as per user request

                content = msg["content"]
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
        text_prompt = st.chat_input("Ask a math question...", disabled=is_processing)
        if text_prompt:
            prompt = text_prompt

    with tab_draw:
        col_canvas, col_controls = st.columns([3, 1])
        with col_canvas:
            canvas_result = st_canvas(
                stroke_width=3, stroke_color="#FFFFFF", background_color="#000000",
                height=300, width=600, drawing_mode="freedraw",
                key=st.session_state.canvas_key,
            )
            draw_prompt_input = st.text_input(
                "Question about drawing (optional)",
                placeholder="Solve this handwritten problem...",
                key="draw_prompt_input"
            )
        with col_controls:
            st.caption("Controls")
            if st.button("Clear"):
                st.session_state.canvas_key = f"canvas_{uuid.uuid4()}"
                st.rerun()
            if st.button("Solve", type="primary", disabled=is_processing):
                if canvas_result.image_data is not None:
                    img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
                    bg  = Image.new("RGB", img.size, (0, 0, 0))
                    bg.paste(img, mask=img.split()[3])
                    buf = io.BytesIO()
                    bg.save(buf, format="PNG")
                    image_b64 = base64.b64encode(buf.getvalue()).decode()
                    prompt = draw_prompt_input or "Solve this handwritten math problem."

    with tab_upload:
        uploaded_file = st.file_uploader("Upload", type=["png", "jpg"], disabled=is_processing)
        upload_prompt_input = st.text_input("Question", placeholder="Analyze...", disabled=is_processing, key="upload_prompt_input")
        if uploaded_file and st.button("Analyze", disabled=is_processing):
            image_b64 = base64.b64encode(uploaded_file.getvalue()).decode()
            prompt    = upload_prompt_input or "Analyze this image."

    # ── 3. New user message → optimistic UI update + rerun ────────────────────
    if prompt:
        req_id = str(uuid.uuid4())
        add_message("user", prompt, image_data=image_b64, request_id=req_id, sent_to_api=False)
        st.session_state.is_processing = True
        st.rerun()

    # ── 4. Fire API call if last message is an unsent user message ────────────
    if (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
        and not st.session_state.messages[-1].get("sent_to_api", False)
    ):
        last = st.session_state.messages[-1]
        request_id = last.get("request_id") or str(uuid.uuid4())
        last["request_id"]  = request_id
        # ✅ CRITICAL: Mark as sent immediately to prevent re-triggering during streaming
        last["sent_to_api"] = True

        with st.chat_message("assistant", avatar="🤖"):
            status_msg = st.status("Thinking...", expanded=False)
            answer_placeholder = st.empty()
            
            full_answer = ""
            logic_trace = []
            
            try:
                # Prepare SSE Session
                payload = {
                    "text": last["content"],
                    "image": last.get("image_data"),
                    "session_id": st.session_state.active_session_id,
                    "request_id": request_id
                }
                headers = get_auth_headers()
                with requests.post(f"{BACKEND_URL}/solve", json=payload, headers=headers, stream=True, timeout=360) as r:
                    if r.status_code == 200:
                        line_buffer = ""
                        last_ui_update = time.time()
                        
                        # ✅ ZERO-BUFFER BYTE STREAMING
                        for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                            if chunk:
                                line_buffer += chunk
                                while "\n" in line_buffer:
                                    line, line_buffer = line_buffer.split("\n", 1)
                                    line = line.strip()
                                    if not line: continue
                                    
                                    try:
                                        if line.startswith("data:"):
                                            line = line[len("data:"):].strip()
                                        
                                        data = json.loads(line)
                                        ev_type = data.get("type", "")
                                        
                                        if ev_type == "answer":
                                            content = data.get("content", "")
                                            full_answer += content
                                            # ✅ RATE-LIMITED UI UPDATE (Smooth @ 20fps)
                                            if time.time() - last_ui_update > 0.05:
                                                answer_placeholder.markdown(full_answer + "▌")
                                                last_ui_update = time.time()
                                        elif ev_type in ("thought", "action", "observation"):
                                            content = data.get("content", "")
                                            if content:
                                                logic_trace.append(content)
                                                status_msg.update(label=f"⚙️ {content}", state="running", expanded=False)
                                    except Exception:
                                        continue
                        
                        # ✅ FINAL FLUSH
                        if line_buffer.strip():
                            try:
                                line = line_buffer.strip()
                                if line.startswith("data:"): line = line[len("data:"):].strip()
                                data = json.loads(line)
                                if data.get("type") == "answer":
                                    full_answer += data.get("content", "")
                            except Exception: pass

                        # Finalize
                        answer_placeholder.markdown(full_answer if full_answer else "No answer received.")
                        status_msg.update(label="Solved!", state="complete", expanded=False)
                        
                        # Save & FINAL SYNC
                        add_message("assistant", full_answer, request_id=request_id)
                        time.sleep(0.1)
                        load_messages(st.session_state.active_session_id)
                        st.rerun()
                    else:
                        st.error(f"Backend Error: {r.status_code}")
            except Exception as e:
                logger.error(f"Streaming Exception: {e}")
                st.error(f"Connection lost or error: {e}")
            finally:
                # ✅ CRITICAL: Always release processing lock
                st.session_state.is_processing = False
                st.rerun()



# ====================================================
# Sidebar
# ====================================================
with st.sidebar:
    st.markdown("### 🧠 MathMinds")
    st.write(f"Logged in as **{st.session_state.user['email']}**")

    view = st.radio(
        "Navigation", ["Chat", "Profile"],
        index=0 if st.session_state.current_view == "Chat" else 1
    )
    if view != st.session_state.current_view:
        st.session_state.current_view = view
        st.rerun()

    if st.button("Sign Out", type="secondary"):
        # ✅ MULTIUSER FIX: Wipe ALL user-specific state first, THEN clear identity.
        # Without _clear_user_state() here, the next user to log in on the same
        # browser tab would see User A's chat history briefly before load_sessions
        # returns, because st.session_state persists across logins within a tab.
        _clear_user_state()
        st.session_state.user = None
        st.rerun()

    if st.session_state.is_processing:
        if st.button(
            "🔓 Reset Processing Lock", type="primary",
            help="Use if UI is stuck despite answer finishing."
        ):
            st.session_state.is_processing = False
            st.rerun()

    st.divider()

    if st.session_state.current_view == "Chat":
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            new_chat()

        st.markdown("#### History")

        for session in st.session_state.chat_sessions:
            sid   = session["session_id"]
            title = session["title"]

            cols = st.columns([0.8, 0.1, 0.1])
            with cols[0]:
                is_active = (st.session_state.active_session_id == sid)
                btn_type  = "primary" if is_active else "secondary"
                if st.button(title, key=f"sel_{sid}", use_container_width=True, type=btn_type):
                    st.session_state.active_session_id = sid
                    load_messages(sid)
                    st.rerun()
            with cols[1]:
                if st.button("🖊️", key=f"ren_{sid}", help="Rename"):
                    st.session_state.renaming_session_id = (
                        sid if st.session_state.renaming_session_id != sid else None
                    )
                    st.rerun()
            with cols[2]:
                if st.button("🗑️", key=f"del_{sid}", help="Delete"):
                    delete_chat(sid)

            if st.session_state.renaming_session_id == sid:
                with st.container():
                    new_title = st.text_input(
                        "New title", value=title,
                        key=f"in_{sid}", label_visibility="collapsed"
                    )
                    if st.button("Save", key=f"save_{sid}", use_container_width=True):
                        rename_chat(sid, new_title)
                        st.session_state.renaming_session_id = None
                        st.rerun()


# ====================================================
# Main Content Area
# ====================================================
if st.session_state.current_view == "Chat":
    chat_interface()
elif st.session_state.current_view == "Profile":
    profile_interface()