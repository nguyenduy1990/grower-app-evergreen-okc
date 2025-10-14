
@echo off
setlocal
cd /d "%~dp0"
set PYEXE=C:\Users\Owner\AppData\Local\Programs\Python\Python313\python.exe
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt
REM Optional: set your OpenAI key for this session
REM set OPENAI_API_KEY=sk-...
"%PYEXE%" app_web.py
