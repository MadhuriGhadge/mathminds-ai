import streamlit as st

st.set_page_config(page_title="Math Solver", page_icon="🧮")

st.title("🧮 Math Solver App")


st.subheader("Enter a Math Problem")
user_text = st.text_area("Type your math problem here")

st.subheader("Or Upload a Problem Image")
uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])

result_placeholder = st.empty()
    
import requests

if st.button("Solve"):
    if user_text:
        response = requests.post(
            "http://localhost:8000/solve_text",
            json={"problem": user_text}
        )
        result = response.json()["solution"]
        result_placeholder.success(result)

    elif uploaded_image:
        files = {"file": (uploaded_image.name, uploaded_image.getvalue())}
        response = requests.post(
            "http://localhost:8000/solve_image",
            files=files
        )
        result = response.json()["solution"]
        result_placeholder.success(result)

    else:
        st.error("Please enter text or upload an image.")

