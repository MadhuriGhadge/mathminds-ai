"""
frontend/app.py — MathMinds AI Streamlit frontend.

STRUCTURE
─────────
  1. CONFIG & CONSTANTS     — env vars, page config, CSS
  2. SESSION STATE          — defaults, init, clear
  3. API LAYER              — all HTTP calls, no st.* calls, returns plain dicts
  4. RENDER HELPERS         — pure display functions, never mutate state
  5. SESSION MANAGEMENT     — state mutations, never call st.rerun()
  6. CHAT INTERFACE         — the 3-state machine (idle / processing / done)
  7. MAIN ENTRY             — auth gate + router

STATE MACHINE (why the previous version had bugs)
──────────────────────────────────────────────────
Every bug in the old version came from collapsing 3 distinct states into one
render pass: add user message + call API + render answer all happened together.

The fix is a strict 3-state machine:

  IDLE        → render history + show input
                user submits → _add_message("user") → is_processing=True → rerun()

  PROCESSING  → render history (user question VISIBLE above spinner)
                make API call → _add_message("assistant") → is_processing=False → rerun()

  IDLE again  → render history (assistant answer now visible)

Rules that make this impossible to break:
  - st.rerun() is ALWAYS the last statement — never inside a with-block
  - The API call NEVER happens inside with st.chat_message()
  - Render helpers never write session_state
  - load_messages() only called on session switch, never after an answer
"""

import streamlit as st
import requests
import base64
import logging
import io
import os
import time
import uuid
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from dotenv import load_dotenv
from firebase_utils import sign_in_with_email, sign_up_with_email, send_password_reset_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONFIG & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "True").lower() == "true"

st.set_page_config(
    page_title="MathMinds AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    .badge {
        display: inline-flex; align-items: center;
        padding: 0.25rem 0.75rem; border-radius: 9999px;
        font-size: 0.75rem; font-weight: 600; margin-right: 0.5rem;
    }
    .badge-blue   { background:rgba(59,130,246,0.2);  color:#93c5fd; border:1px solid rgba(59,130,246,0.3); }
    .badge-purple { background:rgba(168,85,247,0.2);  color:#d8b4fe; border:1px solid rgba(168,85,247,0.3); }
    .badge-green  { background:rgba(34,197,94,0.2);   color:#86efac; border:1px solid rgba(34,197,94,0.3); }
    .badge-red    { background:rgba(239,68,68,0.2);   color:#fca5a5; border:1px solid rgba(239,68,68,0.3); }
    button[kind="primary"] {
        background: linear-gradient(to right, #4f46e5, #7c3aed);
        border: none; box-shadow: 0 4px 6px -1px rgba(79,70,229,0.3); transition: all 0.2s;
    }
    button[kind="primary"]:hover { transform: translateY(-1px); }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULTS = {
    "user":                None,
    "current_view":        "Chat",
    "current_mode":        "solve",
    "chat_sessions":       [],
    "active_session_id":   None,
    "messages":            [],
    "loaded_for_user":     None,
    "loaded_for_session":  None,
    "is_processing":       False,
    "renaming_session_id": None,
    "canvas_key":          "main_canvas",
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Dev mode bypass
if not ENABLE_AUTH and st.session_state.user is None:
    st.session_state.user = {
        "email": "dev@mathminds.ai",
        "token": "mock_dev_token",
        "uid":   "dev_user_123",
    }


def _reset_state(keep_user=False):
    """Clear all state. Optionally preserve the user object."""
    saved_user = st.session_state.user if keep_user else None
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    st.session_state.canvas_key = f"canvas_{uuid.uuid4()}"
    if keep_user:
        st.session_state.user = saved_user


def _get_headers() -> dict:
    u = st.session_state.user
    return {"Authorization": f"Bearer {u['token']}"} if u and "token" in u else {}


def _add_message(role: str, content, **kwargs):
    msg = {"role": role, "content": content, "timestamp": time.time()}
    msg.update(kwargs)
    st.session_state.messages.append(msg)


def _is_blank_canvas(image_data) -> bool:
    if image_data is None:
        return True
    import numpy as np
    return image_data[:, :, 3].max() == 0


# ══════════════════════════════════════════════════════════════════════════════
# 3. API LAYER
# ─────────────────────────────────────────────────────────────────────────────
# Rules:
#   - NO st.* calls anywhere in this section
#   - Returns plain dict, always has "ok" key
#   - Never raises — exceptions are caught and returned as {"ok": False}
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def api_health() -> dict:
    """Cached — only hits the backend once every 30 seconds, not on every rerender."""
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return {"ok": r.status_code == 200, **r.json()} if r.status_code == 200 else {"ok": False}
    except Exception:
        return {"ok": False}


def api_solve(text: str, image, session_id: str, request_id: str, mode: str = "solve") -> dict:
    try:
        r = requests.post(
            f"{BACKEND_URL}/{mode}",
            json={"text": text, "image": image, "session_id": session_id, "request_id": request_id},
            headers=_get_headers(),
            timeout=360,
        )
        if r.status_code == 200:
            return {"ok": True, **r.json()}
        if r.status_code == 401:
            return {"ok": False, "error": "AUTH_EXPIRED"}
        if r.status_code == 429:
            return {"ok": False, "error": "Daily limit reached. Please try again tomorrow."}
        return {"ok": False, "error": f"Backend error {r.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Cannot reach backend. Is the server running?"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "Request timed out."}
    except Exception as e:
        logger.error(f"api_solve: {e}")
        return {"ok": False, "error": "Unexpected error. Please try again."}


def api_load_messages(session_id: str) -> dict:
    try:
        r = requests.get(
            f"{BACKEND_URL}/chat/sessions/{session_id}/messages",
            headers=_get_headers(), timeout=30,
        )
        if r.status_code == 200:   return {"ok": True,  "messages": r.json()}
        if r.status_code == 404:   return {"ok": False, "error": "SESSION_NOT_FOUND"}
        if r.status_code == 401:   return {"ok": False, "error": "AUTH_EXPIRED"}
        return {"ok": False, "error": f"Status {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_load_sessions() -> dict:
    try:
        r = requests.get(f"{BACKEND_URL}/chat/sessions", headers=_get_headers(), timeout=10)
        if r.status_code == 200:   return {"ok": True,  "sessions": r.json()}
        if r.status_code == 401:   return {"ok": False, "error": "AUTH_EXPIRED"}
        return {"ok": False, "error": f"Status {r.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "BACKEND_OFFLINE"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_new_session() -> dict:
    try:
        r = requests.post(f"{BACKEND_URL}/chat/sessions", headers=_get_headers(), timeout=30)
        return {"ok": True, "session": r.json()} if r.status_code == 200 else {"ok": False, "error": f"Status {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_delete_session(sid: str) -> dict:
    try:
        r = requests.delete(f"{BACKEND_URL}/chat/sessions/{sid}", headers=_get_headers(), timeout=30)
        return {"ok": r.status_code == 200}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_rename_session(sid: str, title: str) -> dict:
    try:
        r = requests.patch(
            f"{BACKEND_URL}/chat/sessions/{sid}",
            json={"title": title}, headers=_get_headers(), timeout=30,
        )
        return {"ok": r.status_code == 200}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 4. RENDER HELPERS
# ─────────────────────────────────────────────────────────────────────────────
# Rules:
#   - Only READ session_state, never write
#   - Only call st.* display functions
#   - Never call st.rerun() or make API calls
# ══════════════════════════════════════════════════════════════════════════════

def _badge(source: str, status: str) -> str:
    b = ""
    if source == "sympy_preflight":
        b += '<span class="badge badge-green">⚡ INSTANT</span>'
    elif source in ("cache", "semantic_cache"):
        b += '<span class="badge badge-blue">💾 CACHED</span>'
    elif source in ("google_adk_agent", "agent"):
        b += '<span class="badge badge-purple">🤖 AI</span>'
    if status == "error":
        b += '<span class="badge badge-red">🔴 ERROR</span>'
    return b


def _render_message(msg: dict):
    role = msg.get("role", "assistant")
    with st.chat_message(role, avatar="👤" if role == "user" else "🤖"):
        if role == "user":
            if msg.get("image_data"):
                try:
                    st.image(base64.b64decode(msg["image_data"]), width=300)
                except Exception:
                    pass
            st.write(msg.get("content", ""))
        else:
            meta   = msg.get("metadata") or {}
            status = meta.get("status") or msg.get("status", "success")
            badges = _badge(meta.get("source", ""), status)
            if badges:
                st.markdown(badges, unsafe_allow_html=True)

            logic = meta.get("logic_trace") or msg.get("reasoning")
            if logic:
                steps = [s for s in (logic if isinstance(logic, list) else logic.split("\n")) if s]
                if steps:
                    with st.expander("💭 Reasoning", expanded=False):
                        for step in steps:
                            st.caption(step)

            content = msg.get("content", "")
            if status == "error":
                st.error(content)
            elif isinstance(content, dict) and "final_answer" in content:
                st.markdown(content["final_answer"])
            else:
                st.markdown(str(content))

            # --- EXPORT BUTTONS ---
            if role == "assistant" and status != "error" and content:
                try:
                    from export_utils import generate_latex, compile_pdf
                    
                    msg_id = msg.get("request_id") or str(int(msg.get("timestamp", 0)))
                    pdf_state_key = f"pdf_bytes_{msg_id}"
                    
                    with st.expander("📥 Export Solution (LaTeX / PDF)"):
                        tex_str = generate_latex(str(content))
                        c1, c2 = st.columns(2)
                        
                        with c1:
                            st.download_button(
                                label="📄 Download .tex Source",
                                data=tex_str,
                                file_name=f"mathminds_{msg_id[:8]}.tex",
                                mime="text/plain",
                                key=f"dl_tex_{msg_id}"
                            )
                        
                        with c2:
                            if pdf_state_key not in st.session_state:
                                if st.button("🛠️ Generate PDF", key=f"btn_compile_{msg_id}"):
                                    with st.spinner("Compiling PDF via remote TeX Live..."):
                                        pdf_data = compile_pdf(tex_str)
                                        if pdf_data:
                                            st.session_state[pdf_state_key] = pdf_data
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to compile PDF from external API.")
                            else:
                                st.download_button(
                                    label="✅ Click to Save PDF",
                                    data=st.session_state[pdf_state_key],
                                    file_name=f"mathminds_{msg_id[:8]}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_pdf_{msg_id}"
                                )
                except Exception as e:
                    logger.error(f"Render export error: {e}")


def _render_login():
    _, c, _ = st.columns([1, 2, 1])
    with c:
        st.markdown("""
        <div style="text-align:center;padding:3rem 4rem;background:rgba(255,255,255,0.05);
                    border-radius:20px;border:1px solid rgba(255,255,255,0.1);margin:2rem 0;">
            <h1 style="margin:0">🧠 MathMinds AI</h1>
            <p style="color:#9ca3af;margin-top:0.5rem;">Your intelligent math assistant.</p>
        </div>
        """, unsafe_allow_html=True)

        tab_in, tab_up, tab_reset = st.tabs(["Login", "Sign Up", "Reset Password"])

        with tab_in:
            with st.form("login_form"):
                email    = st.text_input("Email",    placeholder="student@university.edu")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True, type="primary"):
                    if email and password:
                        token, uid, user_email, error = sign_in_with_email(email, password)
                        if token:
                            _reset_state()
                            st.session_state.user = {"email": user_email, "token": token, "uid": uid}
                            st.rerun()
                        else:
                            st.error(f"Login failed: {error}")
                    else:
                        st.error("Please enter email and password.")

        with tab_up:
            with st.form("signup_form"):
                new_email = st.text_input("Email",           placeholder="new@student.edu")
                new_pass  = st.text_input("Password",        type="password")
                confirm   = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True, type="primary"):
                    if new_email and new_pass:
                        if new_pass != confirm:
                            st.error("Passwords do not match.")
                        else:
                            token, uid, user_email, error = sign_up_with_email(new_email, new_pass)
                            if token:
                                _reset_state()
                                st.session_state.user = {"email": user_email, "token": token, "uid": uid}
                                st.rerun()
                            else:
                                st.error(f"Sign up failed: {error}")
                    else:
                        st.error("Please fill all fields.")

        with tab_reset:
            with st.form("reset_form"):
                st.markdown("Enter your email address to receive a secure password reset link.")
                reset_email = st.text_input("Email", placeholder="student@university.edu", key="reset_email_input")
                if st.form_submit_button("Send Reset Link", use_container_width=True, type="primary"):
                    if reset_email:
                        success, error = send_password_reset_email(reset_email)
                        if success:
                            st.success("✅ Password reset link sent! Please check your email inbox.")
                        else:
                            st.error(f"Failed to send reset link: {error}")
                    else:
                        st.error("Please enter your email.")

        st.markdown(
            "<p style='text-align:center;font-size:0.8rem;color:#6b7280;'>Powered by Gemini & SymPy</p>",
            unsafe_allow_html=True,
        )


def _render_profile():
    st.title("👤 User Profile")
    if "profile_data" not in st.session_state:
        try:
            r = requests.get(f"{BACKEND_URL}/users/profile", headers=_get_headers(), timeout=30)
            st.session_state.profile_data = r.json() if r.status_code == 200 else {}
        except Exception:
            st.session_state.profile_data = {}

    data          = st.session_state.profile_data
    levels        = ["High School", "Undergraduate", "Graduate", "Researcher"]
    interests_all = ["Algebra", "Calculus", "Geometry", "Statistics", "Physics", "Computer Science", "Finance"]

    with st.form("profile_form"):
        display_name = st.text_input("Display Name", value=data.get("display_name", ""))
        math_level   = st.selectbox(
            "Math Level", levels,
            index=levels.index(data["math_level"]) if data.get("math_level") in levels else 1,
        )
        interests = st.multiselect(
            "Interests", interests_all,
            default=[i for i in data.get("interests", []) if i in interests_all],
        )
        if st.form_submit_button("Save", use_container_width=True, type="primary"):
            payload = {"display_name": display_name, "math_level": math_level, "interests": interests}
            try:
                r = requests.post(f"{BACKEND_URL}/users/profile", json=payload, headers=_get_headers())
                if r.status_code == 200:
                    st.success("Saved!")
                    st.session_state.profile_data = payload
                else:
                    st.error(f"Failed: {r.text}")
            except Exception as e:
                st.error(str(e))


# ══════════════════════════════════════════════════════════════════════════════
# 5. SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
# These functions mutate session_state but never call st.rerun().
# Callers decide when to rerun.
# ══════════════════════════════════════════════════════════════════════════════

def _refresh_sessions():
    result = api_load_sessions()
    if result["ok"]:
        st.session_state.chat_sessions   = result["sessions"]
        st.session_state.loaded_for_user = st.session_state.user["uid"]
    elif result.get("error") == "AUTH_EXPIRED":
        _reset_state()
    elif result.get("error") == "BACKEND_OFFLINE":
        st.info("⌛ Backend warming up...")
        st.stop()


def _switch_session(sid: str):
    """Load messages for a session. Only fetches if session actually changed."""
    if st.session_state.loaded_for_session == sid:
        st.session_state.active_session_id = sid
        return

    result = api_load_messages(sid)
    if result["ok"]:
        st.session_state.active_session_id  = sid
        st.session_state.messages           = result["messages"]
        st.session_state.loaded_for_session = sid
    elif result.get("error") == "SESSION_NOT_FOUND":
        st.warning("Session not found.")
        st.session_state.active_session_id = None
        st.session_state.messages          = []
    elif result.get("error") == "AUTH_EXPIRED":
        _reset_state()


def _ensure_session() -> bool:
    """
    Make sure there's an active session. Returns True if ready, False if rerun needed.
    """
    if st.session_state.active_session_id:
        return True

    sessions = st.session_state.chat_sessions
    if sessions:
        _switch_session(sessions[0]["session_id"])
        return True

    # Create first session
    result = api_new_session()
    if result["ok"]:
        sess = result["session"]
        st.session_state.active_session_id  = sess["session_id"]
        st.session_state.messages           = []
        st.session_state.loaded_for_session = sess["session_id"]
        _refresh_sessions()
        return False  # caller must rerun
    return True


def _render_sidebar():
    with st.sidebar:
        st.markdown("### 🧠 MathMinds")
        st.caption(f"👤 {st.session_state.user['email']}")

        view = st.radio("Nav", ["Chat", "Profile"],
                        index=0 if st.session_state.current_view == "Chat" else 1,
                        label_visibility="collapsed")
        if view != st.session_state.current_view:
            st.session_state.current_view = view
            st.rerun()

        st.divider()
        st.markdown("#### Mode")
        mode_options = {"solve": "⚡ Solver", "analyze": "🔍 Analyzer", "tutor": "🎓 Tutor"}
        selected = st.selectbox("Select Agent", options=list(mode_options.keys()), format_func=lambda x: mode_options[x], label_visibility="collapsed")
        if selected != st.session_state.current_mode:
            st.session_state.current_mode = selected
            st.rerun()

        # Health
        st.divider()
        health = api_health()
        if health.get("ok"):
            st.markdown('<div class="badge badge-green">● Online</div>', unsafe_allow_html=True)
            svc = health.get("services", {})
            if svc.get("redis") != "healthy":
                st.warning(f"Redis: {svc.get('redis')}")
            if svc.get("mongodb") != "healthy":
                st.warning(f"MongoDB: {svc.get('mongodb')}")
        else:
            st.markdown('<div class="badge badge-red">● Offline</div>', unsafe_allow_html=True)

        # Stuck lock reset
        if st.session_state.is_processing:
            st.divider()
            if st.button("🔓 Reset Lock", help="Use if UI appears stuck"):
                st.session_state.is_processing = False
                st.rerun()

        st.divider()

        if st.session_state.current_view == "Chat":
            if st.button("➕ New Chat", use_container_width=True, type="primary"):
                result = api_new_session()
                if result["ok"]:
                    sess = result["session"]
                    st.session_state.active_session_id  = sess["session_id"]
                    st.session_state.messages           = []
                    st.session_state.loaded_for_session = sess["session_id"]
                    _refresh_sessions()
                    st.rerun()
                else:
                    st.error("Failed to create session.")

            st.markdown("#### History")
            for sess in st.session_state.chat_sessions:
                sid   = sess["session_id"]
                title = sess.get("title", "Chat")
                cols  = st.columns([0.78, 0.11, 0.11])

                with cols[0]:
                    active = st.session_state.active_session_id == sid
                    if st.button(title, key=f"s_{sid}", use_container_width=True,
                                 type="primary" if active else "secondary"):
                        _switch_session(sid)
                        st.rerun()

                with cols[1]:
                    if st.button("✏️", key=f"r_{sid}"):
                        st.session_state.renaming_session_id = (
                            sid if st.session_state.renaming_session_id != sid else None
                        )
                        st.rerun()

                with cols[2]:
                    if st.button("🗑️", key=f"d_{sid}"):
                        api_delete_session(sid)
                        if st.session_state.active_session_id == sid:
                            st.session_state.active_session_id  = None
                            st.session_state.messages           = []
                            st.session_state.loaded_for_session = None
                        _refresh_sessions()
                        st.rerun()

                if st.session_state.renaming_session_id == sid:
                    new_title = st.text_input("Title", value=title,
                                              key=f"ti_{sid}", label_visibility="collapsed")
                    if st.button("Save", key=f"sv_{sid}", use_container_width=True):
                        api_rename_session(sid, new_title)
                        st.session_state.renaming_session_id = None
                        _refresh_sessions()
                        st.rerun()

        st.divider()
        if st.button("Sign Out", use_container_width=True):
            _reset_state()
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 6. CHAT INTERFACE — 3-STATE MACHINE
# ══════════════════════════════════════════════════════════════════════════════

def chat_interface():

    # Ensure active session exists
    if not _ensure_session():
        st.rerun()
        return

    active_sid  = st.session_state.active_session_id
    active_sess = next((s for s in st.session_state.chat_sessions
                        if s["session_id"] == active_sid), None)
    st.title(active_sess["title"] if active_sess else "Chat")

    # ── ALWAYS render history first ────────────────────────────────────────
    # This runs every pass — so the user question is visible while processing
    for msg in st.session_state.messages:
        _render_message(msg)

    # ══════════════════════════════════════════════════════════════════════
    # STATE: PROCESSING
    # Entered when: is_processing=True (user just submitted, prev rerun set flag)
    # Exit: add assistant message → is_processing=False → rerun
    # ══════════════════════════════════════════════════════════════════════
    if st.session_state.is_processing:
        last       = st.session_state.messages[-1]
        request_id = str(uuid.uuid4())

        # Spinner appears BELOW the rendered history (user question visible above)
        with st.spinner("Thinking..."):
            result = api_solve(
                text       = last.get("content", ""),
                image      = last.get("image_data"),
                session_id = active_sid,
                request_id = request_id,
                mode       = st.session_state.current_mode,
            )

        # Auth expired — logout
        if result.get("error") == "AUTH_EXPIRED":
            _reset_state()
            st.rerun()
            return

        # Add assistant response to state
        if result["ok"]:
            answer   = result.get("answer") or "No answer received."
            metadata = result.get("metadata") or {}
            _add_message(
                "assistant", answer,
                request_id = request_id,
                metadata   = {**metadata, "status": result.get("status", "success")},
            )
        else:
            _add_message(
                "assistant", f"⚠️ {result.get('error', 'Unknown error')}",
                request_id = request_id,
                metadata   = {"status": "error"},
            )

        # Transition → IDLE
        # st.rerun() is the LAST statement, outside all with-blocks
        st.session_state.is_processing = False
        st.rerun()
        return

    # ══════════════════════════════════════════════════════════════════════
    # STATE: IDLE
    # Show input. If user submits, transition to PROCESSING.
    # ══════════════════════════════════════════════════════════════════════
    st.divider()
    tab_text, tab_draw, tab_upload = st.tabs(["💬 Text", "✏️ Draw", "📤 Upload"])

    prompt    = None
    image_b64 = None

    with tab_text:
        prompt = st.chat_input("Ask a math question...")

    with tab_draw:
        col_c, col_ctrl = st.columns([3, 1])
        with col_c:
            canvas = st_canvas(
                stroke_width=3, stroke_color="#FFFFFF", background_color="#000000",
                height=300, width=600, drawing_mode="freedraw",
                key=st.session_state.canvas_key,
            )
            draw_q = st.text_input("Question (optional)", placeholder="Solve this...",
                                   key="draw_q")
        with col_ctrl:
            st.caption("Controls")
            if st.button("🗑️ Clear"):
                st.session_state.canvas_key = f"canvas_{uuid.uuid4()}"
                st.rerun()
                return
            if st.button("▶ Solve", type="primary"):
                if canvas.image_data is not None and not _is_blank_canvas(canvas.image_data):
                    img = Image.fromarray(canvas.image_data.astype("uint8"), "RGBA")
                    bg  = Image.new("RGB", img.size, (0, 0, 0))
                    bg.paste(img, mask=img.split()[3])
                    buf = io.BytesIO()
                    bg.save(buf, format="PNG")
                    image_b64 = base64.b64encode(buf.getvalue()).decode()
                    prompt = draw_q or "Solve this handwritten math problem."
                else:
                    st.warning("Please draw something first.")

    with tab_upload:
        uploaded = st.file_uploader("Upload image", type=["png", "jpg"])
        up_q     = st.text_input("Question", placeholder="Analyze...", key="up_q")
        if uploaded and st.button("▶ Analyze", type="primary"):
            image_b64 = base64.b64encode(uploaded.getvalue()).decode()
            prompt    = up_q or "Analyze this image."

    # ── Transition: IDLE → PROCESSING ─────────────────────────────────────
    # Add user message to state, set flag, rerun.
    # The API call happens on the NEXT pass (PROCESSING state above).
    # This is what makes the user question visible before the answer.
    if prompt:
        _add_message("user", prompt, image_data=image_b64)
        st.session_state.is_processing = True
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 7. MAIN ENTRY
# ══════════════════════════════════════════════════════════════════════════════

# Auth gate
if not st.session_state.user:
    _render_login()
    st.stop()

# User switch detection — clear state when a different user logs in
_uid = st.session_state.user["uid"]
if st.session_state.loaded_for_user != _uid:
    _saved = st.session_state.user
    _reset_state()
    st.session_state.user            = _saved
    st.session_state.loaded_for_user = _uid
    _refresh_sessions()

# Sidebar always renders
_render_sidebar()

# Main content
if st.session_state.current_view == "Chat":
    chat_interface()
elif st.session_state.current_view == "Profile":
    _render_profile()