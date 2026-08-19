@echo off
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
    echo Ambiente virtual nao encontrado.
    echo Execute setup.bat primeiro.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python app.py
