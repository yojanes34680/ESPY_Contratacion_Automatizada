@echo off
title Lector Ilustrado
cd /d "%~dp0"
if not exist .venv (
  echo Preparando el programa por primera vez, espere un momento...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt
)
echo Abriendo el Lector Ilustrado en el navegador. No cierre esta ventana mientras lo usa.
.venv\Scripts\python -m lector.servidor
pause
