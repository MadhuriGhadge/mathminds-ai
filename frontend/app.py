import streamlit as st
import requests
import json
import time

# --- Config & Page Setup ---
st.set_page_config(
    page_title="MathMinds AI",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for "Beautiful" UI ---
# Using a dark theme with glassmorphism effects and modern typography
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #0e1117;
        font-family: 'Inter', sans-serif;
    }
    
    /* Title Styling */
    h1 {
        font-weight: 800 !important;
        background: -webkit-linear-gradient(45deg, #FF4B4B, #FF914D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding-bottom: 1rem;
    }
    
    /* Card/Container Styling */
    .css-1r6slb0, .stChatMessage {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        backdrop-filter: blur(10px);
        padding: 15px;
        margin-bottom: 10px;
    }

    /* Button Styling */
    .stButton>button {
        background: linear-gradient(90deg, #FF4B4B 0%, #FF914D 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(255, 75, 75, 0.4);
    }
    
    /* Input Field Styling */
    .stTextInput>div>div>input {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: white;
        border-radius: 10px;
    }
    
    /* Success/Info Box Styling */
    .stSuccess, .stInfo {
        background-color: rgba(0, 200, 83, 0.1);
        border: 1px solid rgba(0, 200, 83, 0.2);
        color: #69f0ae;
    }
    
    /* Hide Streamlit components */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# --- Header ---
col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.title("MathMinds AI")
    st.markdown("<p style='text-align: center; color: #888;'>Your Advanced AI Math Tutor</p>", unsafe_allow_html=True)

st.markdown("---")

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- API Configuration ---
API_URL = "http://localhost:8000/solve"

# --- Sidebar (Settings/Health) ---
with st.sidebar:
    st.header("System Status")
    if st.button("Check Health"):
        try:
            r = requests.get("http://localhost:8000/health", timeout=2)
            if r.status_code == 200:
                st.success("System Online 🟢")
                st.json(r.json())
            else:
                st.error("System Unhealthy 🔴")
        except:
            st.error("Connection Failed 🔴")
            
    st.markdown("---")
    st.markdown("### About")
    st.info("MathMinds uses **Gemini AI** + **Local Reasoning** to solve complex math problems step-by-step.")

# --- Chat Interface ---
# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Enter a math problem..."):
    # Add user message to state
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call API
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        with st.spinner("Solving..."):
            try:
                payload = {"input": prompt}
                response = requests.post(API_URL, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    
                    if status == "success":
                        answer = data.get("answer", "No answer provided.")
                        # Format the output nicely
                        full_response = f"### Solution\n\n{answer}\n"
                        
                        # Add metadata if available (e.g. time taken, steps)
                        # metadata = data.get("metadata", {})
                        # if metadata:
                        #    full_response += f"\n\n*Complexity: {metadata.get('complexity', 'N/A')}*"

                    else:
                        full_response = f"**Status:** {status}\n\nCould not solve the problem."
                        if "error" in data:
                            full_response += f"\nError: {data['error']}"
                else:
                    full_response = f"Error: Server returned status {response.status_code}"
            
            except requests.exceptions.ConnectionError:
                full_response = "❌ **Error:** Could not connect to the backend. Is it running?"
            except Exception as e:
                full_response = f"❌ **Error:** {str(e)}"
        
        # Simulate typing effect for realism (optional, kept fast)
        # for chunk in full_response.split():
        #     time.sleep(0.05)
        #     # ...
        
        message_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})

