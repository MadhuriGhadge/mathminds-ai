import streamlit as st

st.write("start of the script")

if "x" not in st.session_state:
    st.write("initializing x")
    st.session_state.x = 0

st.write("value of x is:",st.session_state.x)

if st.button("increase x"):
    st.session_state.x += 1

st.write("end of script")