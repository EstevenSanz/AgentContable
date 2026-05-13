import re  # Librería para trabajar con expresiones regulares


# =========================
# LIMPIEZA DE TEXTO
# =========================
def limpiar_texto(texto: str):
    """
    Limpia el texto crudo (normalmente de OCR) eliminando caracteres raros
    y normalizando espacios.
    """

    # Reemplaza espacios no separables (muy comunes en OCR/PDF)
    texto = texto.replace("\xa0", " ")

    # Reemplaza tabs por espacios
    texto = texto.replace("\t", " ")

    # Reemplaza múltiples espacios/saltos de línea por un solo espacio
    texto = re.sub(r"\s+", " ", texto)

    # Elimina espacios al inicio y al final
    return texto.strip()


# =========================
#  LIMPIAR NÚMEROS 
# =========================
def limpiar_numero(valor: str):
    """
    Convierte un número en formato texto a float, manejando distintos formatos:
    Ej:
        "1.234,56" -> 1234.56
        "1,234.56" -> 1234.56
        "1 234"    -> 1234
    """

    # Elimina espacios internos
    valor = valor.replace(" ", "")

    # Caso: tiene punto y coma → formato europeo (1.234,56)
    if "." in valor and "," in valor:
        valor = valor.replace(".", "").replace(",", ".")

    # Caso: múltiples puntos → probablemente separadores de miles
    elif valor.count(".") > 1:
        valor = valor.replace(".", "")

    # Caso: solo coma → probablemente separador de miles
    elif "," in valor:
        valor = valor.replace(",", "")

    # Convierte finalmente a número flotante
    return float(valor)


# =========================
#  LÍNEAS
# =========================
def obtener_lineas(texto):
    """
    Divide el texto en líneas limpias (sin vacíos).
    """

    return [l.strip() for l in texto.split("\n") if l.strip()]


# =========================
#  NOMBRE DESDE ARCHIVO
# =========================
def extraer_nombre_archivo(path):
    """
    Extrae un nombre "limpio" a partir del path del archivo.
    """

    # Obtiene solo el nombre del archivo (última parte del path)
    nombre = path.split("\\")[-1].lower()

    # Lista de palabras basura a eliminar
    basura = [
        "pago", "comprobante", "transferencia",
        ".jpg", ".png", ".jpeg", ".pdf"
    ]

    # Elimina palabras irrelevantes
    for b in basura:
        nombre = nombre.replace(b, "")

    # Separa en tokens y elimina palabras cortas (ruido)
    tokens = [t for t in nombre.split() if len(t) > 3]

    # Reconstruye el nombre limpio
    return " ".join(tokens).strip()


# =========================
# VALORES CON $
# =========================
def extraer_valores_con_dolar(texto):
    """
    Extrae todos los valores que tienen símbolo $ en el texto.
    """

    # Busca patrones tipo: $ 1.234,56 o $1234.56
    matches = re.findall(r"\$\s*([\d\.,]+)", texto)

    valores = []
    for m in matches:
        try:
            # Limpia y convierte cada número encontrado
            valores.append(limpiar_numero(m))
        except:
            # Si falla (por formato raro), lo ignora
            pass

    return valores


# =========================
#  TODOS LOS VALORES
# =========================
def extraer_todos_valores(texto):
    """
    Extrae todos los números del texto, incluso sin símbolo $.
    """

    # Busca números con posibles separadores de miles/decimales
    matches = re.findall(r"\d[\d\.,]+\d", texto)

    valores = []
    for m in matches:
        try:
            valores.append(limpiar_numero(m))
        except:
            pass

    return valores


# =========================
#  FILTRAR BASURA
# =========================
def filtrar_valores(valores):
    """
    Elimina valores pequeños que probablemente no son montos relevantes.
    """

    return [v for v in valores if v > 10000]


# =========================
#  VALOR POR CONTEXTO 
# =========================
def extraer_valor_contexto(lineas):
    """
    Busca el valor más confiable usando contexto semántico,
    como líneas que contengan palabras clave.
    """

    for l in lineas:

        l_lower = l.lower()

        # Si la línea contiene palabras clave importantes
        if "valor" in l_lower or "transferencia" in l_lower:

            # Busca un valor con $
            match = re.search(r"\$\s*([\d\.,]+)", l)

            if match:
                try:
                    return limpiar_numero(match.group(1))
                except:
                    pass

    # Si no encuentra nada confiable
    return None


# =========================
#  SELECCIÓN FINAL 
# =========================
def seleccionar_mejor_valor(lineas, valores_con_dolar, todos_valores):
    """
    Selecciona el mejor valor usando una estrategia jerárquica:
    1. Contexto (más confiable)
    2. Valores con $
    3. Valores grandes (fallback)
    """

    # 1. Prioridad máxima: contexto
    valor_ctx = extraer_valor_contexto(lineas)
    if valor_ctx:
        return valor_ctx

    # 2. Valores explícitos con $
    if valores_con_dolar:
        return max(valores_con_dolar)

    # 3. Fallback: valores grandes
    filtrados = filtrar_valores(todos_valores)
    if filtrados:
        return max(filtrados)

    # Si no hay nada útil
    return None


# =========================
# NOMBRES 
# =========================
def extraer_nombres_texto(texto):
    """
    Extrae posibles nombres desde el texto usando mayúsculas.
    """

    # Busca secuencias de palabras en mayúsculas (tipo nombres de empresas/personas)
    nombres = re.findall(r"\b[A-ZÁÉÍÓÚÑ]{4,}(?:\s+[A-ZÁÉÍÓÚÑ]{4,})*\b", texto)

    filtrados = []
    for n in nombres:

        # Evita textos demasiado largos (ruido)
        if len(n) > 40:
            continue

        # Evita frases demasiado largas
        if n.count(" ") > 5:
            continue

        filtrados.append(n)

    return filtrados


# =========================
# PARSER PRINCIPAL 
# =========================
def parsear_imagen(texto, archivo):
    """
    Función principal que procesa una imagen (OCR + metadata)
    y devuelve toda la información estructurada para el matching.
    """

    # Limpia el texto general
    texto_limpio = limpiar_texto(texto)

    # Obtiene líneas originales (para contexto)
    lineas = obtener_lineas(texto)

    # Extrae valores con $
    valores_con_dolar = extraer_valores_con_dolar(texto_limpio)

    # Extrae todos los valores posibles
    todos_valores = extraer_todos_valores(texto_limpio)

    # Selecciona el mejor valor según heurística
    mejor_valor = seleccionar_mejor_valor(
        lineas,
        valores_con_dolar,
        todos_valores
    )

    # Construye el resultado final estructurado
    return {
        "archivo": archivo,  # ruta original
        "lineas": lineas,  # texto dividido por líneas
        "nombre_archivo": extraer_nombre_archivo(archivo),  # nombre limpio
        "valores_con_dolar": valores_con_dolar,  # valores con $
        "valores": todos_valores,  # todos los valores detectados
        "mejor_valor": mejor_valor,  # valor más probable
        "nombres_texto": extraer_nombres_texto(texto),  # posibles nombres detectados
        
    }