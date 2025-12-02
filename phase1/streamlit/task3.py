import streamlit as st

def just_trigger():
    st.write("callback ran but it did not change the input")

name = st.text_input("Name",key="name1",on_change=just_trigger)

st.write("widget value:",name)
st.write("session state:",st.session_state.get("name1"))



if "name2" not in st.session_state:
    st.session_state.name2 = ""

def make_upper():
    st.session_state.name2 = st.session_state.name2.upper()


name = st.text_input("name (auto - uppercase)",key="name2",on_change =  make_upper)

st.write("widget value:",name)
st.write("session state:",st.session_state.name2)


name = st.text_input("name ( manual change button)",key="name3")
if st.button("make uppercase"):
    if "name3" not in st.session_state:
        st.session_state.name3 = st.session_state.name3.upper()
st.write("widget value:",name)
st.write("session state:",st.session_state.name3)

