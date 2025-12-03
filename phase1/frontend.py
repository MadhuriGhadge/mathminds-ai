import streamlit as st
import requests

st.title("🧮 Math Solver")

problem = st.text_area("Enter a math problem")

if st.button("Solve"):
    if not problem:
        st.error("Please enter a problem")
    else:
        response = requests.post(
            "http://localhost:8000/solve",
            json={"problem": problem}
        )
        
        if response.status_code == 200:
            data = response.json()
            st.success(data["solution"])
        else:
            st.error("Error contacting backend")
