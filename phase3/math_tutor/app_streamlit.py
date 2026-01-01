import streamlit as st
from agent import run_math_tutor
from PIL import Image
import os

# Page configuration
st.set_page_config(page_title="MathMinds AI Tutor", page_icon="🎓", layout="centered")

st.title("🎓 MathMinds AI Tutor")
st.markdown("---")

#Chat History in Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for Image Upload
with st.sidebar:
    st.header("Upload Problem")
    uploaded_file = st.file_uploader("Choose a math image...", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="Uploaded Image", use_container_width=True)
        # Save temp file for the agent to read
        with open("sample_math.jpg", "wb") as f:
            f.write(uploaded_file.getbuffer())

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input Box
if prompt := st.chat_input("Ask your math question here..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Tutor Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            image_to_send = "sample_math.jpg" if uploaded_file else None
            response = run_math_tutor(user_input=prompt, image_path=image_to_send)
            st.markdown(response)
    
    # Save assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})