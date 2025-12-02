import streamlit as st 

if "name" not in st.session_state:
    st.session_state.name = ""

st.session_state.name = "XYZ"
name = st.text_input(
    "enter your name:",
    value=st.session_state.name,
    key="name_input"
)

st.write("widget value:",name)
st.write("session state value:", st.session_state.name)

if st.button("save to session"):
    st.session_state.name = name

if st.button("don't save"):
    st.session_state.name = None