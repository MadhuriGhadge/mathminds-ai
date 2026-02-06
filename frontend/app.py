import streamlit as st
import requests
import json
import base64
from PIL import Image
import io
import os
import uuid
import numpy as np
from streamlit_drawable_canvas import st_canvas

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
# Styling
# ====================================================
st.markdown("""
<style>
div[data-testid="stChatMessageUser"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    margin: 8px 0;
}
div[data-testid="stChatMessageAssistant"] {
    background: rgba(255,255,255,0.05);
    border-left: 3px solid #667eea;
    border-radius: 18px;
    padding: 12px 16px;
    margin: 8px 0;
}
.katex { font-size: 1.3em !important; }
</style>
""", unsafe_allow_html=True)

# ====================================================
# Constants
# ====================================================
API_URL = "http://localhost:8000/solve"
HISTORY_FILE = "chat_history.json"

# ====================================================
# Utils
# ====================================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ====================================================
# Session State (IMPORTANT PART)
# ====================================================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_history()

if "active_session_id" not in st.session_state:
    sid = str(uuid.uuid4())
    st.session_state.chat_sessions[sid] = {"title": "New Chat", "messages": []}
    st.session_state.active_session_id = sid
    save_history(st.session_state.chat_sessions)

# 🔒 STABLE CANVAS KEY (THIS FIXES YOUR BUG)
if "canvas_key" not in st.session_state:
    st.session_state.canvas_key = "main_canvas"

if "show_canvas" not in st.session_state:
    st.session_state.show_canvas = False

# ====================================================
# Helpers
# ====================================================
def messages():
    return st.session_state.chat_sessions[st.session_state.active_session_id]["messages"]

def add_message(role, content, **extra):
    msg = {"role": role, "content": content}
    msg.update(extra)
    st.session_state.chat_sessions[st.session_state.active_session_id]["messages"].append(msg)
    save_history(st.session_state.chat_sessions)

def clear_canvas():
    # ONLY time we change key
    st.session_state.canvas_key = f"canvas_{uuid.uuid4()}"

def toggle_canvas_preview():
    st.session_state.show_canvas = not st.session_state.show_canvas

# ====================================================
# Sidebar
# ====================================================
with st.sidebar:
    st.title("🧠 MathMinds AI")

    if st.button("➕ New Chat", use_container_width=True):
        sid = str(uuid.uuid4())
        st.session_state.chat_sessions[sid] = {"title": "New Chat", "messages": []}
        st.session_state.active_session_id = sid
        save_history(st.session_state.chat_sessions)
        st.rerun()

    st.divider()
    model_choice = st.radio("Model", ["Standard (Flash)", "Advanced (Pro)"])

    # --- State Init ---
    if "deleted_session" not in st.session_state:
        st.session_state.deleted_session = None

    # --- Search ---
    search_query = st.text_input("🔍 Search chats", placeholder="Type to filter...", label_visibility="collapsed")
    
    # --- Undo Logic ---
    if st.session_state.deleted_session:
        col_undo, _ = st.columns([0.8, 0.2])
        with col_undo:
            if st.button("↩️ Undo Delete", type="secondary", use_container_width=True):
                # Restore
                deleted = st.session_state.deleted_session
                st.session_state.chat_sessions[deleted["id"]] = deleted["data"]
                st.session_state.active_session_id = deleted["id"]
                st.session_state.deleted_session = None
                save_history(st.session_state.chat_sessions)
                st.toast("Chat restored! 🎉")
                st.rerun()

    st.divider()
    
    # --- Sorting & Filtering ---
    # 1. Filter
    all_sessions = []
    for sid, s in st.session_state.chat_sessions.items():
        # Default pinned to False if missing
        if "pinned" not in s: 
            s["pinned"] = False
            
        if not search_query or (search_query.lower() in s["title"].lower()):
            all_sessions.append((sid, s))
    
    # 2. Sort: Pinned first, then by insertion order (reversed)
    # Python dicts preserve insertion order (lifo for reverse)
    # We want pinned items at top, staying in their relative order, then unpinned.
    # Actually, simplest is two lists.
    pinned_sessions = [x for x in all_sessions if x[1]["pinned"]]
    regular_sessions = [x for x in all_sessions if not x[1]["pinned"]]
    
    # Reverse regular so new is top (if we assume dict keys are chronologically increasing or insertion order)
    # Since we are iterating dict items, it's insertion order.
    regular_sessions = regular_sessions[::-1] 
    pinned_sessions = pinned_sessions[::-1] # Newest pinned top too
    
    sorted_display = pinned_sessions + regular_sessions

    st.subheader("History")

    for sid, s in sorted_display:
        is_active = (sid == st.session_state.active_session_id)
        
        # --- Active Session Rendering ---
        if is_active:
            # Inline Rename
            with st.container():
                col_mark, col_input = st.columns([0.15, 0.85])
                with col_mark:
                    st.write("👉")
                with col_input:
                    new_title = st.text_input(
                        "Rename", 
                        value=s["title"], 
                        key=f"rename_{sid}", 
                        label_visibility="collapsed"
                    )
                    if new_title != s["title"]:
                        st.session_state.chat_sessions[sid]["title"] = new_title
                        save_history(st.session_state.chat_sessions)
                        st.rerun()
            
            # Action Buttons Row
            c1, c2, c3 = st.columns(3)
            with c1:
                # Pin Toggle
                pin_icon = "📍" if s["pinned"] else "📌"
                if st.button(pin_icon, key=f"pin_{sid}", help="Pin/Unpin"):
                    st.session_state.chat_sessions[sid]["pinned"] = not st.session_state.chat_sessions[sid]["pinned"]
                    save_history(st.session_state.chat_sessions)
                    st.rerun()
            with c2:
                # Delete Popover
                with st.popover("🗑️", help="Delete"):
                    st.write("Confirm delete?")
                    if st.button("Yes, Delete", key=f"confirm_del_{sid}"):
                        # Save for undo
                        st.session_state.deleted_session = {"id": sid, "data": st.session_state.chat_sessions[sid]}
                        
                        # Delete
                        del st.session_state.chat_sessions[sid]
                        
                        # Switch active
                        if st.session_state.chat_sessions:
                            st.session_state.active_session_id = list(st.session_state.chat_sessions.keys())[-1]
                        else:
                            # Create new if clean slate
                            new_id = str(uuid.uuid4())
                            st.session_state.chat_sessions[new_id] = {"title": "New Chat", "messages": []}
                            st.session_state.active_session_id = new_id
                        
                        save_history(st.session_state.chat_sessions)
                        st.toast("Chat deleted. Undo available!")
                        st.rerun()

        # --- Inactive Session Rendering ---
        else:
            name_display = f"{'📌 ' if s['pinned'] else ''}{s['title']}"
            if st.button(name_display, key=f"btn_{sid}", use_container_width=True):
                st.session_state.active_session_id = sid
                st.rerun()


# ====================================================
# Main UI
# ====================================================
st.markdown("### 🎓 MathMinds AI")
st.caption("Ask, upload, or draw a math problem")

# ====================================================
# Render Chat
# ====================================================
for m in messages():
    avatar = "👤" if m["role"] == "user" else "🤖"
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])
        if m.get("image_data"):
            st.image(base64.b64decode(m["image_data"]), width=200)
        if m.get("reasoning"):
            with st.expander("Steps"):
                st.markdown(m["reasoning"])

# ====================================================
# Input Processing
# ====================================================
def process_input(text, image_b64=None, preview=None):
    with st.chat_message("user", avatar="👤"):
        if text:
            st.markdown(text)
        if preview:
            st.image(preview, width=200)

    add_message("user", text or "Analyze image", image_data=image_b64)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            payload = {
                "text": text,
                "image": image_b64,
                "model_preference": "reasoning" if "Advanced" in model_choice else "fast"
            }
            try:
                r = requests.post(API_URL, json=payload, timeout=120)
                data = r.json()

                if data["status"] != "success":
                    st.error(data.get("error", "Error"))
                    return

                ans = data["answer"]
                if ans.get("latex"):
                    st.latex(ans["latex"])

                st.markdown(f"**Answer:**\n\n> {ans['final_answer']}")

                with st.expander("Steps"):
                    st.markdown(ans.get("reasoning", ""))

                add_message(
                    "assistant",
                    f"**Answer:**\n\n> {ans['final_answer']}",
                    reasoning=ans.get("reasoning", "")
                )
            except Exception as e:
                st.error(f"Error: {e}")
                add_message("assistant", f"Error: {e}")

# ====================================================
# Tabs
# ====================================================
tab_upload, tab_draw = st.tabs(["📤 Upload", "✏️ Draw"])

# ---------------- Upload ----------------
with tab_upload:
    uploaded = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"])
    if uploaded and st.button("✨ Analyze Upload", use_container_width=True):
        b64 = base64.b64encode(uploaded.getvalue()).decode()
        process_input("Solve this image problem", b64, uploaded)
        st.rerun()

# ---------------- Draw ----------------
with tab_draw:
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        mode = st.selectbox("Tool", ["freedraw", "line", "rect", "circle", "transform"])
    with c2:
        width = st.slider("Brush", 1, 25, 6)
    with c3:
        color = st.color_picker("Color", "#FFFFFF")
    with c4:
        st.button("🗑️ Clear", on_click=clear_canvas, use_container_width=True)
    with c5:
        st.button(
            "👁️ Show" if not st.session_state.show_canvas else "🙈 Hide",
            on_click=toggle_canvas_preview,
            use_container_width=True
        )

    # 🔥 CANVAS (NOW ALWAYS RENDERS)
    canvas = st_canvas(
        key=st.session_state.canvas_key,
        height=400,
        width=1000,
        drawing_mode=mode,
        stroke_width=width,
        stroke_color=color,
        background_color="#1E1E1E",
        update_streamlit=True
    )

    # Preview Section
    if st.session_state.show_canvas and canvas.image_data is not None:
        with st.expander("Canvas Preview (what AI sees)", expanded=True):
            st.image(
                canvas.image_data,
                caption="RGBA Canvas Output",
                width="stretch"
            )

    if st.button("✨ Solve Sketch", use_container_width=True):
        if canvas.image_data is None:
            st.warning("Draw something first")
        else:
            img = Image.fromarray(canvas.image_data.astype("uint8"), "RGBA")
            bg = Image.new("RGB", img.size, (0, 0, 0))
            bg.paste(img, mask=img.split()[3])

            buf = io.BytesIO()
            bg.save(buf, format="PNG")

            b64 = base64.b64encode(buf.getvalue()).decode()
            process_input("Solve this drawn problem", b64, bg)
            st.rerun()

# ====================================================
# Text Input
# ====================================================
if prompt := st.chat_input("Ask your math question..."):
    process_input(prompt)
    st.rerun()
