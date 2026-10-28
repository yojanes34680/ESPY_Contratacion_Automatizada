@echo off
chcp 65001 >nul
title Desactivar Inicio Automático - ESPY
cd /d "%~dp0"

echo ======================================================================
echo    DESACTIVAR INICIO AUTOMÁTICO CON WINDOWS - ESPY CONTRATACIÓN
echo ======================================================================
echo.

powershell -ExecutionPolicy Bypass -Command "
$startupFolder = [System.Environment]::GetFolderPath('Startup')
$targetScript = Join-Path $startupFolder 'ESPY_Autoinicio_Servidor.vbs'
if (Test-Path $targetScript) {
    Remove-Item $targetScript -Force
    Write-Host '[EXITO] Se ha removido el inicio automatico de Windows.' -ForegroundColor Green
    Write-Host 'Ahora deberas iniciar el sistema manualmente con el acceso directo cuando lo necesites.' -ForegroundColor Yellow
} else {
    Write-Host 'El inicio automatico no estaba configurado.' -ForegroundColor Cyan
}
"

echo.
timeout /t 3 >nul
