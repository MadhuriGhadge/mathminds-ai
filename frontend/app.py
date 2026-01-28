import streamlit as st
import requests
import json
import base64
from PIL import Image
import io

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

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

# --- API Config ---
API_URL = "http://localhost:8000/solve"

# --- Sidebar ---
with st.sidebar:
    st.title("🧠 MathMinds")
    
    # New Chat Button
    if st.button("➕ New session", type="primary", width="stretch"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.subheader("Input Options")
    
    # Image Uploader in Sidebar for cleanliness
    uploaded_file = st.file_uploader(
        "Attach Image (Optional)", 
        type=['png', 'jpg', 'jpeg'], 
        help="Upload a math problem image to analyze."
    )
    
    if uploaded_file:
        st.image(uploaded_file, caption="Attached Image", width="stretch")
        # Convert to Base64 immediately for use
        bytes_data = uploaded_file.getvalue()
        base64_image = base64.b64encode(bytes_data).decode('utf-8')
    else:
        base64_image = None

    st.markdown("---")
    st.caption(f"Session ID: {st.session_state.session_id[:8]}...")
    st.caption("Powered by Gemini")

# --- Chat Interface ---

# Header
st.markdown("### 🎓 MathMinds AI Assistant")
st.caption("Ask a math question or upload an image to get a step-by-step solution.")

# 1. Render Chat History
for msg in st.session_state.messages:
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
            # Reconstruct image from base64 for display (optional, if we want to show it in chat stream)
            # For now, we rely on the text indicating attachment or just sidebar.
            # Let's show a small thumbnail if user attached it.
            try:
                img_bytes = base64.b64decode(msg["image_data"])
                st.image(img_bytes, caption="Uploaded Problem", width=200)
            except:
                pass


# 2. Input Handling
if prompt := st.chat_input("Ask your math question..."):
    
    # --- OPTIMISTIC UI UPDATE ---
    # Display User Message Immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
        if base64_image:
             st.image(uploaded_file, width=200)
             st.caption("Image attached")

    # Save to history
    user_msg_obj = {"role": "user", "content": prompt}
    if base64_image:
        user_msg_obj["image_data"] = base64_image
    st.session_state.messages.append(user_msg_obj)

    # --- API CALL ---
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Analyzing problem..."):
            try:
                # Prepare Payload (Multi-modal)
                payload = {
                    "text": prompt,
                    "image": base64_image # Optional
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
                        
                        # 1. Display Final Answer prominently
                        st.markdown(f"**Answer:**\n\n> {final_ans}")
                        
                        # 2. Display LaTeX if available (Context)
                        if latex_prob:
                            st.caption("Problem Interpretation:")
                            st.latex(latex_prob)
                            
                        # 3. Logic Expander
                        with st.expander("Show Step-by-Step Logic"):
                            st.markdown(reasoning)
                            
                        # Save to history
                        asst_msg_obj = {
                            "role": "assistant", 
                            "content": f"**Answer:**\n\n> {final_ans}",
                            "reasoning": reasoning
                        }
                        st.session_state.messages.append(asst_msg_obj)
                        
                    else:
                        error_msg = data.get("error") or "Unknown error occurred."
                        st.error(f"AI Error: {error_msg}")
                        st.session_state.messages.append({"role": "assistant", "content": f"Error: {error_msg}"})
                        
                else:
                    st.error(f"Server Error {response.status_code}")
                    
            except Exception as e:
                st.error(f"Connection Failed: {str(e)}")
