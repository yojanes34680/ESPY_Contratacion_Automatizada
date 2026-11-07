"""``python -m psr_midi`` abre la ventana; con argumentos funciona por consola."""
import sys

if len(sys.argv) > 1:
    from .cli import main

    raise SystemExit(main())

from .gui import main

main()
