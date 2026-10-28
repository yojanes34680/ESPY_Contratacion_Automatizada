@echo off
chcp 65001 >nul
title Detener Servidor ESPY
cd /d "%~dp0"

echo ======================================================================
echo    DETENER SERVIDOR ESPY CONTRATACIÓN
echo ======================================================================
echo.

powershell -Command "
$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($c in $conns) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($p) {
            Write-Host ('Deteniendo proceso: ' + $p.ProcessName + ' (PID: ' + $p.Id + ')') -ForegroundColor Yellow
            Stop-Process -Id $p.Id -Force
        }
    }
    Write-Host 'Servidor ESPY detenido con exito.' -ForegroundColor Green
} else {
    Write-Host 'No se encontro ningun servidor ESPY corriendo en el puerto 8000.' -ForegroundColor Cyan
}
"

echo.
timeout /t 3 >nul
