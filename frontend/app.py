import streamlit as st
import requests
import json
import base64
from PIL import Image
import io
import os

# --- Page Config ---
st.set_page_config(
    page_title="MathMinds AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Themes & Styles ---
# Note: Colors are mainly handled by .streamlit/config.toml, 
# but we add some specific overrides for Chat elements here.
st.markdown("""
<style>
    /* Chat Container Tweaks */
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 10px;
    }
    
    /* User Message Style */
    div[data-testid="stChatMessage"][data-testid="stChatMessageUser"] {
        background-color: rgba(26, 115, 232, 0.1); /* Subtle Blue Tint */
    }
    
    /* Assistant Message Style */
    div[data-testid="stChatMessage"][data-testid="stChatMessageAssistant"] {
        background-color: rgba(255, 255, 255, 0.05); /* Subtle overlay */
    }

    /* LaTeX Font */
    .katex { font-size: 1.1em !important; }
</style>
""", unsafe_allow_html=True)

# --- History Management ---
HISTORY_FILE = "chat_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            # If error (e.g. empty file), return empty
            return {}
    return {}

def save_history(sessions):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

# --- Session Initialization ---
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_history()

if "active_session_id" not in st.session_state:
    # If sessions exist, pick the first one (or ideally latest)
    if st.session_state.chat_sessions:
        # Sort by creation or modification if we had timestamps, for now just keys
        st.session_state.active_session_id = list(st.session_state.chat_sessions.keys())[0]
    else:
        # Create default first session
        import uuid
        new_id = str(uuid.uuid4())
        st.session_state.chat_sessions[new_id] = {"title": "New Chat", "messages": []}
        st.session_state.active_session_id = new_id
        save_history(st.session_state.chat_sessions)

if "session_id" not in st.session_state:
    # Legacy fallback, sync with active
    st.session_state.session_id = st.session_state.active_session_id

# Helper to get current messages
def get_current_messages():
    return st.session_state.chat_sessions[st.session_state.active_session_id]["messages"]

# Helper to add message to current session
def add_message(role, content, **kwargs):
    session = st.session_state.chat_sessions[st.session_state.active_session_id]
    msg_obj = {"role": role, "content": content, **kwargs}
    session["messages"].append(msg_obj)
    
    # Update title if it's the first user message and title is generic
    if role == "user" and session["title"] == "New Chat":
        # simple truncation for title
        session["title"] = content[:30] + "..." if len(content) > 30 else content
        
    save_history(st.session_state.chat_sessions)

def delete_session(session_id):
    if session_id in st.session_state.chat_sessions:
        del st.session_state.chat_sessions[session_id]
        save_history(st.session_state.chat_sessions)
        
        # If we deleted the active session, switch to another
        if session_id == st.session_state.active_session_id:
            # Pick first available, or create new if empty
            if st.session_state.chat_sessions:
                st.session_state.active_session_id = list(st.session_state.chat_sessions.keys())[0]
            else:
                # Create default first session
                import uuid
                new_id = str(uuid.uuid4())
                st.session_state.chat_sessions[new_id] = {"title": "New Chat", "messages": []}
                st.session_state.active_session_id = new_id
                save_history(st.session_state.chat_sessions)
        
        st.rerun()

# --- API Config ---
API_URL = "http://localhost:8000/solve"

# --- Sidebar ---
with st.sidebar:
    st.title("🧠 MathMinds")
    
    # New Chat Button
    if st.button("➕ New session", type="primary", use_container_width=True):
        import uuid
        new_id = str(uuid.uuid4())
        st.session_state.chat_sessions[new_id] = {"title": "New Chat", "messages": []}
        st.session_state.active_session_id = new_id
        save_history(st.session_state.chat_sessions)
        st.rerun()

    st.markdown("---")
    st.subheader("Settings")
    model_choice = st.radio(
        "Reasoning Model",
        ["Standard (Flash)", "Advanced (Pro)"],
        index=0,
        help="Use Standard for speed, Advanced for complex visual reasoning."
    )
    
    st.markdown("---")
    st.subheader("History")
    
    # Active Session Rename (if exists)
    active_id = st.session_state.active_session_id
    if active_id in st.session_state.chat_sessions:
        curr_title = st.session_state.chat_sessions[active_id].get("title", "New Chat")
        new_title = st.text_input("Current Title", value=curr_title, key=f"rename_{active_id}")
        if new_title != curr_title:
            st.session_state.chat_sessions[active_id]["title"] = new_title
            save_history(st.session_state.chat_sessions)
            st.rerun()
    
    # List previous sessions
    session_ids = list(st.session_state.chat_sessions.keys())[::-1]
    
    for sid in session_ids:
        session = st.session_state.chat_sessions[sid]
        title = session.get("title", "New Chat")
        
        col1, col2 = st.columns([0.85, 0.15])
        
        with col1:
             # Highlight active
            if sid == st.session_state.active_session_id:
                st.button(f"👉 {title}", key=f"btn_{sid}", disabled=True, use_container_width=True)
            else:
                if st.button(title, key=f"btn_{sid}", use_container_width=True):
                    st.session_state.active_session_id = sid
                    st.rerun()
        
        with col2:
            if st.button("🗑️", key=f"del_{sid}", help="Delete Session"):
                delete_session(sid)

    st.markdown("---")
    st.caption(f"Active ID: {st.session_state.active_session_id[:8]}...")
    st.caption("Powered by Gemini")

# --- Chat Interface ---

# Header
st.markdown("### 🎓 MathMinds AI")
st.caption("Ask a math question or upload an image to get a step-by-step solution.")

# 1. Render Chat History for Active Session
current_messages = get_current_messages()

for msg in current_messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        # Render Text
        st.markdown(msg["content"])
        
        # Render Logic Expander (for Assistant)
        if msg.get("reasoning"):
            with st.expander("Show Step-by-Step Logic"):
                st.markdown(msg["reasoning"])
        
        # Render Attached Image (for User)
        if msg.get("image_data"):
            try:
                img_bytes = base64.b64decode(msg["image_data"])
                st.image(img_bytes, caption="Uploaded Problem", width=200)
            except:
                pass


# 2. Input Handling Logic - Reused for both Text and Image-only flows
def process_input(prompt_text, image_b64=None, display_image=None):
    """
    Handles the UI and API logic for a new user message.
    """
    if not prompt_text and not image_b64:
        return

    # --- OPTIMISTIC UI UPDATE ---
    # Display User Message Immediately
    with st.chat_message("user", avatar="👤"):
        if prompt_text:
            st.markdown(prompt_text)
        if display_image:
             st.image(display_image, width=200)
             st.caption("Image attached")

    # Save to history via helper
    msg_kwargs = {}
    if image_b64:
        msg_kwargs["image_data"] = image_b64
    add_message("user", prompt_text or "Analyze this image.", **msg_kwargs)


    # --- API CALL ---
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Analyzing problem..."):
            try:
                # Map UI choice to API value
                pref_map = {
                    "Standard (Flash)": "fast",
                    "Advanced (Pro)": "reasoning"
                }
                model_pref = pref_map.get(model_choice, "fast")

                # Prepare Payload (Multi-modal)
                payload = {
                    "text": prompt_text,
                    "image": image_b64, # Optional
                    "model_preference": model_pref
                }
                
                response = requests.post(API_URL, json=payload, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data["status"] == "success":
                        answer_data = data.get("answer", {})
                        
                        # Extract components
                        latex_prob = answer_data.get("latex", "")
                        reasoning = answer_data.get("reasoning", "")
                        final_ans = answer_data.get("final_answer", "")
                        
                        # 1. Display LaTeX if available (Context) - High Priority
                        if latex_prob:
                            st.caption("Problem Interpretation:")
                            st.latex(latex_prob)

                        # 2. Display Final Answer prominently
                        st.markdown(f"**Answer:**\n\n> {final_ans}")
                            
                        # 3. Logic Expander
                        with st.expander("Show Step-by-Step Logic"):
                            st.markdown(reasoning)
                            
                        # Save to history via helper
                        add_message("assistant", f"**Answer:**\n\n> {final_ans}", reasoning=reasoning)
                        
                    else:
                        error_msg = data.get("error") or "Unknown error occurred."
                        st.error(f"AI Error: {error_msg}")
                        add_message("assistant", f"Error: {error_msg}")
                        
                else:
                    st.error(f"Server Error {response.status_code}")
                    
            except Exception as e:
                st.error(f"Connection Failed: {str(e)}")
                # Retry Button
                if st.button("🔄 Retry Request", type="primary"):
                    process_input(prompt_text, image_b64, display_image)
                    st.rerun()


# 3. Input Controls (Main Area)
# Place Image Uploader in an expander nicely above input
with st.expander("📎 Attach Image", expanded=False):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Upload math problem", 
            type=['png', 'jpg', 'jpeg'], 
            label_visibility="collapsed"
        )
    
    # Analyze Image Button
    with col2:
        analyze_btn = st.button("✨ Analyze Image", type="primary", use_container_width=True)

# Prepare image data if present
base64_image = None
if uploaded_file:
    bytes_data = uploaded_file.getvalue()
    base64_image = base64.b64encode(bytes_data).decode('utf-8')
    st.image(uploaded_file, width=150, caption="Attached")

# Logic:
# 1. Click "Analyze Image" -> Triggers process_input with image + default text
# 2. Type text + Enter -> Triggers process_input with text + image (if attached)

if analyze_btn:
    if uploaded_file:
        process_input(
            prompt_text="Please solve the problem in this image.",
            image_b64=base64_image,
            display_image=uploaded_file
        )
        st.rerun() # Rerun to update chat history
    else:
        st.warning("Please upload an image first.")

if prompt := st.chat_input("Ask your math question..."):
    process_input(
        prompt_text=prompt,
        image_b64=base64_image,
        display_image=uploaded_file
    )
    st.rerun()
