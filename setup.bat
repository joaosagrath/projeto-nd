@echo off
cd /d %~dp0

if not exist .venv (
    py -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Ambiente configurado com sucesso.
echo Para iniciar o Fluxar Emissões, execute run.bat.
pause
