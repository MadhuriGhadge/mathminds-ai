import streamlit as st
def update_name():
    st.session_state.name_updated = st.session_state.name_input.upper()

st.text_input("enter name:",key="name_input",on_change=update_name)

st.write("original:",st.session_state.get("name_input"))
st.write("updated:",st.session_state.get("name_updated"))