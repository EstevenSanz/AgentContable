# Importamos fuzz de thefuzz, que permite comparar strings de forma difusa
# (útil cuando hay errores de escritura u OCR)
# pyrefly: ignore [missing-import]
from thefuzz import fuzz


def nombre_match_basico(nombre_registro, nombre_archivo):
    """
    Esta función determina si dos nombres (registro vs archivo)
    probablemente hacen referencia a la misma entidad/persona.

    Retorna:
        True  -> si encuentra coincidencia razonable
        False -> si no encuentra nada
    """

    # Convertimos el nombre del registro a minúsculas y lo separamos en palabras (tokens)
    tokens_reg = nombre_registro.lower().split()

    # Normalizamos el nombre del archivo:
    # - minúsculas
    # - reemplazamos "_" y "-" por espacios
    # - dividimos en tokens
    tokens_arch = (
        nombre_archivo.lower()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )

    # Recorremos cada palabra del nombre del registro
    for t in tokens_reg:

        # Ignoramos palabras muy cortas (ruido como "SAS", "LTD", etc.)
        if len(t) <= 3:
            continue

        # Comparamos contra cada token del nombre del archivo
        for ta in tokens_arch:

            # 1. Coincidencia directa parcial
            # Ej: "pablo" en "pablo123"
            if t in ta or ta in t:
                return True

            # 2. Coincidencia difusa (fuzzy matching)
            # Calcula similitud entre strings (0 a 100)
            score = fuzz.ratio(t, ta)

            # Si la similitud es suficientemente alta, lo consideramos match
            if score >= 80:
                return True

    # Si no encontramos ninguna coincidencia
    return False


def generar_candidatos(registro, imagenes):
    """
    Filtra las imágenes para quedarse solo con aquellas que
    probablemente coincidan con el registro.

    Si no encuentra candidatos, devuelve todas las imágenes
    (fallback para no perder matches).
    """

    candidatos = []

    # Recorremos todas las imágenes
    for img in imagenes:

        # Si el nombre del registro coincide con el nombre del archivo
        if nombre_match_basico(registro["nombre"], img["nombre_archivo"]):
            candidatos.append(img)

    # Si no encontramos ningún candidato,
    # usamos todas las imágenes (estrategia de respaldo)
    if not candidatos:
        candidatos = imagenes

    return candidatos


def score_match(registro, imagen):
    """
    Calcula un puntaje que indica qué tan bien una imagen
    coincide con un registro.

    Mientras mayor el score, mejor el match.
    """

    score = 0  # Inicializamos el puntaje

    # Obtenemos valores monetarios
    valor_reg = registro.get("debito")
    valor_img = imagen.get("mejor_valor")

    # ========================
    # 1. COMPARACIÓN DE VALOR
    # ========================
    if valor_img is not None and valor_reg is not None:

        # Diferencia absoluta entre valores
        diff = abs(valor_img - valor_reg)

        # Mientras más cercanos, mayor puntaje
        if diff < 5:
            score += 80  # match casi exacto
        elif diff < 1000:
            score += 50  # match cercano
        elif diff < 10000:
            score += 20  # match débil

    # ========================
    # 2. NOMBRE DEL ARCHIVO
    # ========================
    # Si el nombre coincide, sumamos puntos
    if nombre_match_basico(registro["nombre"], imagen.get("nombre_archivo", "")):
        score += 30

    # ========================
    # 3. TEXTO OCR
    # ========================
    # Revisamos los nombres detectados dentro de la imagen
    for n in imagen.get("nombres_texto", []):

        # Si alguno coincide con el registro
        if nombre_match_basico(registro["nombre"], n):
            score += 10  # suma pequeña pero útil
            break  # no seguimos buscando más

    return score


def match_imagenes_con_principal(registros, imagenes):
    """
    Función principal:
    Para cada registro, encuentra la mejor imagen asociada.

    Retorna una lista de resultados con:
    - registro
    - imagen seleccionada
    - score obtenido
    """

    resultados = []

    # Recorremos todos los registros
    for reg in registros:

        # Generamos candidatos (filtrado previo)
        candidatos = generar_candidatos(reg, imagenes)

        mejor = None        # mejor imagen encontrada
        mejor_score = -1    # mejor puntaje encontrado

        # Debug: cuántos candidatos hay
        print("\nCANDIDATOS:", len(candidatos))

        # Evaluamos cada candidato
        for img in candidatos:

            # Calculamos el score entre registro e imagen
            s = score_match(reg, img)

            # Si encontramos un mejor score, lo actualizamos
            if s > mejor_score:
                mejor_score = s
                mejor = img

        # Si el score es positivo, aceptamos el match
        if mejor_score > 0:
            imagen_final = mejor
        else:
            imagen_final = None  # no hay match válido

        # Guardamos el resultado
        resultados.append({
            "registro": reg,
            "imagen": imagen_final,
            "score": mejor_score
        })

    return resultados