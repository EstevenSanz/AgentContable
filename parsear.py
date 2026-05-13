import re


def limpiar_numero(valor: str) -> float:

    valor = valor.strip()

    
    if "," in valor and "." in valor:
        if valor.rfind(",") > valor.rfind("."):
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", "")

    
    elif "," in valor:
        valor = valor.replace(",", ".")

   
    else:
        valor = valor

    return float(valor)


def parsear_principal(texto: str):

    lineas = [
        l.replace("\xa0", " ").replace("\t", " ").strip()
        for l in texto.split("\n")
        if l.strip()
    ]

    resultado = []

    documento_principal = ""
    fecha = ""

    # HEADER
    for linea in lineas:

        if "DOCUMENTO" in linea:
            match = re.search(r"DOCUMENTO\s*:\s*(\d+)", linea)
            if match:
                documento_principal = match.group(1)

        if re.match(r"\d{2}\s\d{2}\s\d{4}", linea):
            fecha = linea

    # ROWS
    inicio_tabla = False

    for linea in lineas:

        if "CUENTA DESCRIPCION" in linea:
            inicio_tabla = True
            continue

        if not inicio_tabla:
            continue

        if "Elaborado" in linea:
            break

        registro = parsear_fila(linea, fecha, documento_principal)

        if registro:
            resultado.append(registro)

    return resultado


def parsear_fila(linea, fecha, documento_principal):

    pattern = r"""
        ^(?P<cuenta>\S+)\s+
        (?P<descripcion>.*?)\s+
        (?P<valor>[\d,]+\.\d{2})\s+
        (?P<nit>[\d\.-]+)\s+
        (?P<nombre>.*?)\s+
        (?P<documento_cliente>\S+)$
    """

    match = re.match(pattern, linea, re.VERBOSE)

    if not match:
        print("NO MATCH:", repr(linea))
        return None

    if "CUENTA" in linea and "DESCRIPCION" in linea:
        print("TABLA DETECTADA")                

    

    return {
        "fecha": fecha,
        "documento_principal": documento_principal,
        "nit": match.group("nit"),
        "nombre": match.group("nombre"),
        "documento_cliente": match.group("documento_cliente"),
        "descripcion": match.group("descripcion"),
        "debito": limpiar_numero(match.group("valor")),
        "credito": 0
    }