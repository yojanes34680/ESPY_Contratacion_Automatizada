"""Utility to convert numeric currency values to Spanish words for Colombian legal contracts."""

UNIDADES = (
    "", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"
)

DECENAS = (
    "", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", 
    "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"
)

DIEZ_Y = (
    "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", 
    "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"
)

VEINTI_Y = (
    "VEINTE", "VEINTIÚN", "VEINTIDÓS", "VEINTITRÉS", "VEINTICUATRO", 
    "VEINTICINCO", "VEINTISÉIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE"
)

CENTENAS = (
    "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", 
    "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"
)

def _tres_digitos_a_palabras(n: int) -> str:
    """Convierte un número entre 0 y 999 a palabras en español."""
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    
    c = n // 100
    resto = n % 100
    d = resto // 10
    u = resto % 10

    texto_c = CENTENAS[c]

    if resto == 0:
        return texto_c
    
    if resto < 10:
        texto_du = UNIDADES[u]
    elif 10 <= resto <= 19:
        texto_du = DIEZ_Y[resto - 10]
    elif 20 <= resto <= 29:
        texto_du = VEINTI_Y[resto - 20]
    else:
        if u == 0:
            texto_du = DECENAS[d]
        elif u == 1:
            texto_du = f"{DECENAS[d]} Y UN"
        else:
            texto_du = f"{DECENAS[d]} Y {UNIDADES[u]}"

    if texto_c:
        return f"{texto_c} {texto_du}".strip()
    return texto_du.strip()

def numero_a_letras_cop(valor: float) -> str:
    """
    Convierte una cifra numérica a su representación legal en pesos colombianos.
    Ejemplo: 15450000 -> 'QUINCE MILLONES CUATROCIENTOS CINCUENTA MIL PESOS MONEDA CORRIENTE (M/CTE)'
    """
    if valor is None:
        return "CERO PESOS MONEDA CORRIENTE (M/CTE)"
    
    entero = int(round(valor))
    if entero == 0:
        return "CERO PESOS MONEDA CORRIENTE (M/CTE)"

    if entero < 0:
        return f"MENOS {numero_a_letras_cop(abs(entero))}"

    partes = []

    # Billones (si aplica)
    billones = entero // 1_000_000_000_000
    resto = entero % 1_000_000_000_000

    if billones == 1:
        partes.append("UN BILLÓN")
    elif billones > 1:
        partes.append(f"{_tres_digitos_a_palabras(billones)} BILLONES")

    # Miles de millones
    miles_millones = resto // 1_000_000_000
    resto = resto % 1_000_000_000

    # Millones
    millones = resto // 1_000_000
    resto = resto % 1_000_000

    total_millones = (miles_millones * 1000) + millones
    if total_millones == 1:
        partes.append("UN MILLÓN")
    elif total_millones > 1:
        if miles_millones > 0:
            partes.append(f"{_tres_digitos_a_palabras(miles_millones)} MIL {_tres_digitos_a_palabras(millones)} MILLONES".replace("  ", " ").strip())
        else:
            partes.append(f"{_tres_digitos_a_palabras(millones)} MILLONES")

    # Miles
    miles = resto // 1000
    resto = resto % 1000

    if miles == 1:
        partes.append("UN MIL")
    elif miles > 1:
        partes.append(f"{_tres_digitos_a_palabras(miles)} MIL")

    # Centenas/Decenas/Unidades restantes
    if resto > 0:
        partes.append(_tres_digitos_a_palabras(resto))

    texto_final = " ".join([p for p in partes if p]).strip()
    de_conector = " DE" if (entero >= 1_000_000 and entero % 1_000_000 == 0) else ""
    return f"{texto_final}{de_conector} PESOS MONEDA CORRIENTE (M/CTE)"
