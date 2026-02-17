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

# Load env immediately
load_dotenv()

# ====================================================
# Page Config
# ====================================================
st.set_page_config(
    page_title="MathMinds AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================================================
# Premium Global Styling (Glassmorphism + Typography)
# ====================================================
st.markdown("""
<style>
    /* Global Background */
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgb(17 24 39) 0%, rgb(10 10 10) 90%);
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Chat Bubbles */
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
    
    /* Typography */
    h1, h2, h3 {
        color: #f3f4f6;
        letter-spacing: -0.5px;
    }
    p, li {
        color: #e5e7eb;
        line-height: 1.6;
    }
    
    /* Canvas Container */
    .canvas-container {
        border-radius: 12px;
        overflow: hidden;
        border: 2px solid rgba(99, 102, 241, 0.3);
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.1);
    }

    /* Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    .badge-blue { background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-purple { background: rgba(168, 85, 247, 0.2); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3); }
    .badge-green { background: rgba(34, 197, 94, 0.2); color: #86efac; border: 1px solid rgba(34, 197, 94, 0.3); }
    
    /* Buttons */
    button[kind="primary"] {
        background: linear-gradient(to right, #4f46e5, #7c3aed);
        border: none;
        box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.3);
        transition: all 0.2s;
    }
    button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 8px -1px rgba(79, 70, 229, 0.4);
    }

</style>
""", unsafe_allow_html=True)

# ====================================================
# Config & State
# ====================================================
API_URL = "http://localhost:8000/solve" # Ensure this matches implementation
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

# Auth State (Mocked for UI demo, replace with real Firebase token logic)
if "user" not in st.session_state:
    st.session_state.user = None # {"email": "demo@user.com", "token": "mock_token"}

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
            # Switch to another or create new
            if st.session_state.chat_sessions:
                 st.session_state.active_session_id = list(st.session_state.chat_sessions.keys())[0]
            else:
                 new_chat()
        save_history()
        st.rerun()

# ====================================================
# Login Screen (Simple Overlay)
# ====================================================
def login_screen():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.write("")
        st.write("")
        st.markdown("""
        <div style="text-align: center; padding: 4rem; background: rgba(255,255,255,0.05); border-radius: 20px; border: 1px solid rgba(255,255,255,0.1);">
            <h1>🧠 MathMinds AI</h1>
            <p style="color: #9ca3af;">Your intelligent quantitative assistant.</p>
        </div>
        """, unsafe_allow_html=True)
        
        
        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
        
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="student@university.edu")
                password = st.text_input("Password", type="password")
                
                submitted = st.form_submit_button("Sign In", use_container_width=True)
                if submitted:
                    if email and password:
                        api_key = os.getenv("FIREBASE_WEB_API_KEY")
                        if not api_key:
                            st.error("Missing FIREBASE_WEB_API_KEY in .env")
                        else:
                            try:
                                # Firebase Identity Toolkit API - Login
                                auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                                payload = {"email": email, "password": password, "returnSecureToken": True}
                                r = requests.post(auth_url, json=payload)
                                
                                if r.status_code == 200:
                                    auth_data = r.json()
                                    st.session_state.user = {
                                        "email": auth_data["email"], 
                                        "token": auth_data["idToken"], 
                                        "uid": auth_data["localId"]
                                    }
                                    st.success(f"Welcome back, {auth_data['email']}!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    err_msg = r.json().get("error", {}).get("message", "Login Failed")
                                    st.error(f"Login Failed: {err_msg}")
                            except Exception as e:
                                st.error(f"Connection Error: {e}")
                    else:
                        st.error("Please enter email and password.")

        with tab_signup:
            with st.form("signup_form"):
                new_email = st.text_input("New Email", placeholder="new@student.edu")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                signup_submitted = st.form_submit_button("Create Account", use_container_width=True)
                
                if signup_submitted:
                    if new_email and new_password:
                        if new_password != confirm_password:
                            st.error("Passwords do not match!")
                        else:
                            api_key = os.getenv("FIREBASE_WEB_API_KEY")
                            if not api_key:
                                st.error("Missing FIREBASE_WEB_API_KEY in .env")
                            else:
                                try:
                                    # Firebase Identity Toolkit API - Sign Up
                                    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
                                    payload = {"email": new_email, "password": new_password, "returnSecureToken": True}
                                    r = requests.post(auth_url, json=payload)
                                    
                                    if r.status_code == 200:
                                        auth_data = r.json()
                                        st.session_state.user = {
                                            "email": auth_data["email"], 
                                            "token": auth_data["idToken"], 
                                            "uid": auth_data["localId"]
                                        }
                                        st.success(f"Account Created! Welcome, {auth_data['email']}!")
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        err_msg = r.json().get("error", {}).get("message", "Sign Up Failed")
                                        st.error(f"Sign Up Failed: {err_msg}")
                                except Exception as e:
                                    st.error(f"Connection Error: {e}")
                    else:
                        st.error("Please fill all fields.")
        
        st.markdown("<p style='text-align: center; font-size: 0.8rem; color: #6b7280;'>Powered by Gemini 1.5 Pro & SymPy</p>", unsafe_allow_html=True)

if not st.session_state.user:
    login_screen()
    st.stop() # Stop rendering the rest until logged in

# ====================================================
# Main App Layout
# ====================================================

# ====================================================
# Main App Logic
# ====================================================

def profile_interface():
    st.title("👤 User Profile")
    st.markdown("Customize your MathMinds experience.")
    
    # Fetch current profile
    headers = {"Authorization": f"Bearer {st.session_state.user['token']}"}
    
    # Use session state to avoid re-fetching on every rerun if possible, 
    # but for simplicity we fetch or check state
    if "profile_data" not in st.session_state:
        try:
            r = requests.get(f"{API_URL.replace('/solve', '')}/users/profile", headers=headers)
            if r.status_code == 200:
                st.session_state.profile_data = r.json()
            else:
                st.error("Failed to load profile.")
                st.session_state.profile_data = {}
        except Exception as e:
            st.error(f"Connection error: {e}")
            st.session_state.profile_data = {}
            
    data = st.session_state.profile_data
    
    with st.form("profile_form"):
        display_name = st.text_input("Display Name", value=data.get("display_name", ""))
        math_level = st.selectbox(
            "Math Proficiency Level",
            ["High School", "Undergraduate", "Graduate", "Researcher"],
            index=["High School", "Undergraduate", "Graduate", "Researcher"].index(data.get("math_level", "Undergraduate")) if data.get("math_level") in ["High School", "Undergraduate", "Graduate", "Researcher"] else 1
        )
        
        current_interests = data.get("interests", [])
        all_interests = ["Algebra", "Calculus", "Geometry", "Statistics", "Physics", "Computer Science", "Finance"]
        interests = st.multiselect("Areas of Interest", all_interests, default=[i for i in current_interests if i in all_interests])
        
        submitted = st.form_submit_button("Save Profile", use_container_width=True, type="primary")
        
        if submitted:
            payload = {
                "display_name": display_name,
                "math_level": math_level,
                "interests": interests
            }
            try:
                r = requests.post(f"{API_URL.replace('/solve', '')}/users/profile", json=payload, headers=headers)
                if r.status_code == 200:
                    st.success("Profile updated successfully!")
                    st.session_state.profile_data = payload # Update local cache
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Update failed: {r.text}")
            except Exception as e:
                st.error(f"Error saving: {e}")

def chat_interface():
    # --- Active Chat Interface ---
    if st.session_state.active_session_id not in st.session_state.chat_sessions:
         new_chat() # fallback
         
    st.title(st.session_state.chat_sessions[st.session_state.active_session_id]["title"])

    # 1. Render Chat History
    session = get_active_session()
    for msg in session["messages"]:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                if msg.get("image_data"):
                    st.image(base64.b64decode(msg["image_data"]), width=300)
                st.write(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                # Metadata Badges
                meta = msg.get("metadata", {})
                if meta:
                    badges_html = ""
                    if meta.get("source") == "deterministic":
                        badges_html += '<span class="badge badge-green">⚡ SYMBOLIC</span>'
                    elif meta.get("source") == "cache":
                        badges_html += '<span class="badge badge-blue">💾 CACHED</span>'
                    elif meta.get("source") == "agent":
                        badges_html += '<span class="badge badge-purple">🤖 AGENT</span>'
                    
                    model = meta.get("model_used")
                    if model:
                       badges_html += f'<span class="badge" style="background: rgba(255,255,255,0.1);">{model}</span>'
                    
                    st.markdown(badges_html, unsafe_allow_html=True)
                
                # Content
                content = msg["content"]
                
                # If complex reasoning exists
                reasoning = msg.get("reasoning")
                if reasoning:
                    with st.expander("Show Reasoning Steps"):
                        st.markdown(reasoning)
                
                # Final Answer
                if isinstance(content, dict) and "final_answer" in content:
                    st.markdown(f"**Answer:**\n\n> {content['final_answer']}")
                else:
                    st.markdown(content)


    # 2. Input Area (Tabs for Text / Image / Canvas)
    st.divider()
    tab_text, tab_draw, tab_upload = st.tabs(["💬 Text", "✏️ Draw", "📤 Upload"])

    prompt = None
    image_b64 = None

    # Processing Flag
    is_processing = st.session_state.get("is_processing", False)

    with tab_text:
        prompt = st.chat_input("Ask a math question...", disabled=is_processing)

    with tab_draw:
        col_canvas, col_controls = st.columns([3, 1])
        with col_canvas:
            # Drawing Canvas
            if "canvas_key" not in st.session_state: st.session_state.canvas_key = "main_canvas"
            
            canvas_result = st_canvas(
                stroke_width=3,
                stroke_color="#FFFFFF",
                background_color="#000000",
                height=300,
                width=600,
                drawing_mode="freedraw",
                key=st.session_state.canvas_key,
            )
            
            draw_prompt = st.text_input("Question about drawing (optional)", placeholder="Solve this handwritten math problem...")
            
        with col_controls:
            st.caption("Controls")
            if st.button("Clear Canvas"):
                st.session_state.canvas_key = f"canvas_{uuid.uuid4()}"
                st.rerun()
            
            if st.button("Solve Drawing", type="primary", disabled=is_processing):
                if canvas_result.image_data is not None:
                    # Convert to b64
                    img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
                    # Composite over black
                    bg = Image.new("RGB", img.size, (0, 0, 0))
                    bg.paste(img, mask=img.split()[3])
                    
                    buf = io.BytesIO()
                    bg.save(buf, format="PNG")
                    image_b64 = base64.b64encode(buf.getvalue()).decode()
                    prompt = draw_prompt if draw_prompt else "Solve this handwritten math problem."

    with tab_upload:
        uploaded = st.file_uploader("Upload Image", type=["png", "jpg"], disabled=is_processing)
        upload_prompt = st.text_input("Question about image (optional)", placeholder="Analyze this image...", disabled=is_processing)
        
        if uploaded and st.button("Analyze Image", disabled=is_processing):
            image_b64 = base64.b64encode(uploaded.getvalue()).decode()
            prompt = upload_prompt if upload_prompt else "Analyze this image."


    # 3. Processing Logic
    if prompt:
        # Optimistic UI Update
        # Generate strict request_id here to guarantee 1:1 mapping with user input
        req_id = str(uuid.uuid4())
        # Add message with sent_to_api=False (will be set to True before actual call)
        add_message("user", prompt, image_data=image_b64, request_id=req_id, sent_to_api=False)
        
        # Set processing flag
        st.session_state.is_processing = True
        st.rerun()

    # Check if last message was user, trigger AI response
    # Strict Gating: Only proceed if NOT already sent to API
    if (
        session["messages"] 
        and session["messages"][-1]["role"] == "user" 
        and not session["messages"][-1].get("sent_to_api", False)
    ):
        last_msg = session["messages"][-1]
        
        # Retrieve persistent request_id
        current_request_id = last_msg.get("request_id")
        if not current_request_id:
             # Fallback for old messages or if something went wrong
             current_request_id = str(uuid.uuid4())
             last_msg["request_id"] = current_request_id
             save_history()
        
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Agent is thinking... (Calling tools)"):
                try:
                    # MARK AS SENT BEFORE CALLING
                    last_msg["sent_to_api"] = True
                    save_history()

                    # Payload
                    payload = {
                        "text": last_msg["content"],
                        "image": last_msg.get("image_data"),
                        "model_preference": "agent",
                        "session_id": st.session_state.active_session_id,
                        "request_id": current_request_id # Use persistent ID
                    }
                    
                    # HEADERS with Auth
                    headers = {}
                    if st.session_state.user:
                         headers["Authorization"] = f"Bearer {st.session_state.user['token']}"
                    
                    response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
                    data = response.json()
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get("status") == "success":
                            # Standardize answer extraction
                            answer_raw = data.get("answer")
                            content_to_save = ""
                            
                            if isinstance(answer_raw, dict):
                                 content_to_save = answer_raw.get("final_answer") or answer_raw.get("text") or str(answer_raw)
                            else:
                                 content_to_save = str(answer_raw)
                            
                            # Use top-level explanation from schema
                            explanation = data.get("explanation")
                            
                            add_message(
                                "assistant", 
                                content_to_save, 
                                reasoning=explanation,
                                metadata=data.get("metadata"),
                                steps=data.get("steps") # New field
                            )
                            st.rerun()
                            st.session_state.is_processing = False
                            st.rerun()
                            st.session_state.is_processing = False
                            st.rerun()
                        elif response.status_code in [202, 409]:
                            # Silent handling for duplicates or processing
                            # Just clear flag and rerun, no noise
                            st.session_state.is_processing = False
                            st.rerun()
                        else:
                            error_msg = data.get("error", "Unknown error")
                            st.error(f"API Error: {error_msg}")
                            add_message("assistant", f"⚠️ Error: {error_msg}")
                            st.session_state.is_processing = False
                            st.rerun() # Ensure we close the turn
                    else:
                        st.error(f"Server Error: {response.status_code}")
                        # Try to parse error details
                        try:
                            err_data = response.json()
                            err_msg = err_data.get("error", "Unknown Server Error")
                        except:
                            err_msg = f"HTTP {response.status_code}"
                        
                        st.rerun()
                except Exception as e:
                    st.error(f"Connection Failed: {e}")
                    # CRITICAL FIX: Add error message to history to stop retry loop
                    add_message("assistant", f"❌ Connection Failed: {str(e)}")
                    st.session_state.is_processing = False
                    st.rerun()

# --- Initialize View State ---
if "current_view" not in st.session_state:
    st.session_state.current_view = "Chat"

# --- Sidebar (History & Settings) ---
with st.sidebar:
    st.markdown("### 🧠 MathMinds")
    
    st.write(f"Logged in as **{st.session_state.user['email']}**")
    
    # Navigation
    view = st.radio("Navigation", ["Chat", "Profile"], index=0 if st.session_state.current_view == "Chat" else 1)
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
        
        # Sort by recent
        sorted_sids = sorted(
            st.session_state.chat_sessions.keys(), 
            key=lambda k: st.session_state.chat_sessions[k].get("created_at", 0), 
            reverse=True
        )
        
        for sid in sorted_sids:
            sess = st.session_state.chat_sessions[sid]
            title = sess.get("title", "Untitled")
            isActive = (sid == st.session_state.active_session_id)
            
            col_nav, col_del = st.columns([0.85, 0.15])
            with col_nav:
                if st.button(f"{'📍 ' if isActive else ''}{title}", key=sid, use_container_width=True):
                       st.session_state.active_session_id = sid
                       st.rerun()
            with col_del:
                if isActive:
                     if st.button("🗑️", key=f"del_{sid}"):
                          delete_chat(sid)

# --- Router ---
if st.session_state.current_view == "Profile":
    profile_interface()
else:
    chat_interface()


