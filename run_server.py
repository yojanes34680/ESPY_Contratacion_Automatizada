import os
import sys
import socket
import uvicorn
from pathlib import Path

# Agregar la carpeta backend al sys.path para importaciones directas
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

def get_local_ip():
    """Detecta la IP real de este equipo en la red local (Wi-Fi/Ethernet)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    # Asegurar codificacion UTF-8 para consola de Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    lan_ip = get_local_ip()
    hostname = socket.gethostname()

    print("=" * 72)
    print(" ESPY - Sistema de Contratacion Automatizada para Empresas de Servicios Publicos")
    print(" Regimen: Ley 142 de 1994 (Derecho Privado sujeto a Principios de Gestion Fiscal)")
    print("=" * 72)
    print(f" Estado: Servidor ACTIVO y escuchando en toda la red (0.0.0.0:{port})")
    print("-" * 72)
    print(f"  * Tu enlace (este computador):       http://127.0.0.1:{port}/app/")
    print(f"  * Enlace para Invitados (Wi-Fi/LAN):  http://{lan_ip}:{port}/app/")
    print(f"  * Enlace por Nombre de Red:          http://{hostname}:{port}/app/")
    print(f"  * Documentacion API Swagger:         http://127.0.0.1:{port}/docs")
    print("=" * 72)
    print(" NOTA: Para que los invitados (celulares, laptops) puedan entrar,")
    print(f" deben estar en la misma red Wi-Fi y abrir: http://{lan_ip}:{port}/app/")
    print(" Manten esta ventana abierta mientras utilices el sistema.")
    print("=" * 72 + "\n")

    uvicorn.run("app.main:app", host=host, port=port, reload=True)

