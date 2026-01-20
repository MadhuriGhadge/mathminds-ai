@echo off
echo Starting MathMinds UI...
call .venv\Scripts\activate
streamlit run frontend/app.py
pause
