import streamlit as st 

# state initialization
if "counter" not in st.session_state:
    st.session_state.counter = 0

#create buttons
col1,col2,col3 = st.columns(3)

#modify state based on clicks
with col1:
    if st.button("increase"):
        st.session_state.counter += 1
with col2:
    if st.button("decrement"):
        st.session_state.counter -=1
with col3:
    if st.button("reset"):
        st.session_state.counter = 0

#show counter
st.write("counter: ",st.session_state.counter)

