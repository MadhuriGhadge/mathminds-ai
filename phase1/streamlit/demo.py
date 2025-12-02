import streamlit as st
st.write("app loaded.")
text = st.text_input("type something")
st.write("you typed:",text)

age = st.slider("Your age", 0, 100)


count = 0

#'''if st.button("increase"):
#    count += 1
#st.write("count =",count)
#'''

if "count" not in st.session_state:
    st.session_state.count = 0

if st.button("increase"):
    st.session_state.count += 1

st.write("count =", st.session_state.count)