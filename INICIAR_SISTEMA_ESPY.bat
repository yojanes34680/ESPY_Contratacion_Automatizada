@echo off
chcp 65001 >nul
title ESPY - Sistema de Contratación Automatizada
cd /d "%~dp0"

echo ======================================================================
echo    ESPY - SISTEMA DE CONTRATACIÓN AUTOMATIZADA (LEY 142 DE 1994)
echo ======================================================================
echo.

:: 1. Detectar ejecutable de Python
set "PYTHON_EXE="
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=py"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] No se encontro Python en el sistema.
    echo Por favor asegurese de tener Python 3 instalado.
    pause
    exit /b 1
)

:: 2. Verificar si el servidor ya esta corriendo en el puerto 8000
netstat -ano | findstr /R ":8000.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] El servidor ya se encuentra ACTIVO en el puerto 8000.
    echo Abriendo la aplicacion en su navegador web...
    start "" "http://127.0.0.1:8000/app/"
    echo.
    echo Listo. Puede cerrar esta ventana si lo desea.
    timeout /t 5 >nul
    exit /b 0
)

:: 3. Abrir el navegador automaticamente tras 3 segundos
echo [INFO] Iniciando el servidor del sistema...
start /b powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8000/app/'"

:: 4. Ejecutar el servidor
"%PYTHON_EXE%" run_server.py

if errorlevel 1 (
    echo.
    echo [AVISO] El servidor se ha detenido.
    pause
)
