@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  Instalando Cancion a MIDI para Yamaha PSR-S950
echo ============================================================
where python >nul 2>nul || (
  echo No se encontro Python. Instale Python 3.11 desde https://www.python.org/downloads/
  echo y marque la casilla "Add python.exe to PATH".
  pause & exit /b 1
)
where ffmpeg >nul 2>nul || (
  echo Instalando ffmpeg ^(necesario para leer MP3 y MP4^)...
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
)
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Instalando motores de inteligencia artificial (puede tardar y descargar ~2 GB)...
pip install -r requirements-ia.txt
echo.
echo Instalacion terminada. Use INICIAR_CONVERTIDOR.bat para abrir el programa.
pause
