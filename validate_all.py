"""Envoltura de validate_all.py que ejecuta la suite de validación aislada en tests/test_validate_all.py."""
import sys
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent
    cmd = [sys.executable, "-m", "pytest", "tests/test_validate_all.py", "-v"]
    print(f">>> Ejecutando suite de validacion oficial mediante pytest...")
    ret = subprocess.call(cmd, cwd=str(root_dir))
    sys.exit(ret)

if __name__ == "__main__":
    main()
