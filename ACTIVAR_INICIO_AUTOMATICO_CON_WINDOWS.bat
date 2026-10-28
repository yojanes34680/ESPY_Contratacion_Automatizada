@echo off
chcp 65001 >nul
title Activar Inicio Automático con Windows - ESPY
cd /d "%~dp0"

echo ======================================================================
echo    CONFIGURAR INICIO AUTOMÁTICO CON WINDOWS - ESPY CONTRATACIÓN
echo ======================================================================
echo.
echo Este asistente configurará el servidor ESPY para que se inicie
echo automáticamente y en segundo plano cada vez que enciendas tu computador.
echo De esta forma:
echo   1. Nunca más te saldrá "No se puede acceder a este sitio web".
echo   2. http://127.0.0.1:8000/app/ estará siempre disponible.
echo   3. Tus compañeros e invitados podrán conectarse siempre sin pedirte
echo      que inicies el sistema.
echo.

powershell -ExecutionPolicy Bypass -Command "
$startupFolder = [System.Environment]::GetFolderPath('Startup')
$targetScript = Join-Path $startupFolder 'ESPY_Autoinicio_Servidor.vbs'
$projectDir = (Get-Location).Path
$pythonw = 'C:\Users\Usuario\AppData\Local\Programs\Python\Python314\pythonw.exe'

if (-not (Test-Path $pythonw)) {
    $pyCmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pyCmd) { $pythonw = $pyCmd.Source } else { $pythonw = 'pythonw.exe' }
}

$vbsContent = @'
Set WshShell = CreateObject(""WScript.Shell"")
WshShell.CurrentDirectory = ""{0}""
WshShell.Run ""\""{1}\"" run_server.py"", 0, False
'@ -f $projectDir, $pythonw

[System.IO.File]::WriteAllText($targetScript, $vbsContent, [System.Text.Encoding]::ASCII)
Write-Host ('[EXITO] Se ha creado el archivo de inicio automatico en:' + $startupFolder) -ForegroundColor Green
Write-Host 'A partir de tu proximo inicio de Windows, el servidor ESPY estara siempre activo.' -ForegroundColor Cyan
"

echo.
echo Presiona cualquier tecla para salir...
pause >nul
