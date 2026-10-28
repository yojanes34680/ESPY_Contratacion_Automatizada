@echo off
chcp 65001 >nul
echo =====================================================================
echo  Habilitando Regla de Firewall para ESPY Contratación (Puerto 8000)
echo =====================================================================
echo.
netsh advfirewall firewall add rule name="ESPY Contratacion Server (Puerto 8000)" dir=in action=allow protocol=TCP localport=8000 profile=any
if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] Regla creada exitosamente. El puerto 8000 ahora acepta conexiones entrantes de la red local.
) else (
    echo.
    echo [ERROR] No se pudo crear la regla. Recuerda ejecutar este archivo haciendo clic derecho y eligiendo "Ejecutar como administrador".
)
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul
