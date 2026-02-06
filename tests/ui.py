import streamlit as st
from streamlit_drawable_canvas import st_canvas

st.title("Canvas Debugger")
# Minimal possible canvas
canvas_result = st_canvas(
    stroke_width=5,
    stroke_color="#FF0000",
    background_color="#000000",
    height=400,
    width=600,
    drawing_mode="freedraw",
    key="debug_canvas"
)
st.write("Is there image data?", canvas_result.image_data is not None)