import os
import re
import shutil
import subprocess
import json
import google.genai as genai
from datetime import datetime
from thefuzz import fuzz
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN ---
# API Key hardcoded (idealmente usar variable de entorno)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCH_FOLDER = os.path.join(BASE_DIR, "input")
BASE_OUTPUT = os.path.join(BASE_DIR, "output")

# Regex para el protocolo "Prefijo-ID"
# Sintaxis: {ID_Lote}-{Tipo_Documento}-{Descripción}.{ext}
FILE_PATTERN = r"^(\d+)-([^-]+)-([^\.]+)\.(.+)$"

def extraer_datos_egreso_ia(ruta_archivo):
    """Fase 2 (Prioritaria): La IA lee el Egreso para metadatos."""
    print(f"[*] Intentando extracción con Gemini IA...")
    # Prompt enfocado en los campos solicitados
    contents = """
    Analiza este Comprobante de Egreso. Extrae:
    1. NIT y Nombre del proveedor (en la tabla).
    2. Total DEBITOS.
    3. DOCUMENTO (referencia de factura).
    4. Nombre del CLIENTE (encabezado, ej: 'Tangible').
    5. FECHA (para determinar mes y año).

    Responde SOLAMENTE en JSON válido con estas claves:
    {"nit": "...", "nombre": "...", "monto": 0.0, "ref_factura": "...", "cliente": "...", "fecha": "YYYY-MM-DD"}
    """
    try:
        imagen_o_pdf = client.files.upload(file=ruta_archivo)
        response = client.models.generate_content(
            model="gemini-2.5-flash", # Usamos flash para rapidez/costo
            contents=[contents, imagen_o_pdf],
            config=genai.types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        raise Exception(f"Fallo Gemini IA: {e}")

def extraer_datos_egreso_local(ruta_archivo):
    """Fase 2 (Fallback): Extrae datos del PDF usando pdftotext y Regex."""
    print(f"[*] Intentando extracción LOCAL (Regex)...")
    try:
        # Ejecutar pdftotext para obtener el texto plano
        result = subprocess.run(['pdftotext', '-layout', ruta_archivo, '-'], capture_output=True, text=True, check=True)
        texto = result.stdout
        lines = texto.split('\n')

        datos = {
            "cliente": None,
            "fecha": None,
            "nit": None,
            "nombre": None,
            "ref_factura": None,
            "monto": 0.0 # Opcional si no se usa para validación
        }

        # 1. CLIENTE: Generalmente en la primera línea
        if lines:
            datos['cliente'] = lines[0].strip()

        # 2. FECHA: Buscar patrón DD MM YYYY o YYYY/MM/DD
        # En el PDF ejemplo aparece como: 03     12     2025
        fecha_match = re.search(r'(\d{2})\s+(\d{2})\s+(\d{4})', texto)
        if fecha_match:
            dia, mes, anio = fecha_match.groups()
            datos['fecha'] = f"{anio}-{mes}-{dia}"
        
        # 3. DATOS DE TABLA (NIT, NOMBRE, DOCUMENTO)
        # Buscamos líneas que contengan el patrón de NIT: 900.403.508-4
        for line in lines:
            # Regex para fila de transacción: ... NIT NOMBRE DOCUMENTO
            # Ejemplo: ... 900.403.508-4 MÁSCAPACIDAD S.A.S   000TPC407
            # Ejemplo 2: ... 98.634.925-5 HUMBERTO ANTONIO OC 000002285 (NIT con 2 digitos al inicio)
            # Ejemplo 3: ... 901.578.815-5 TENI INSUMOS S A S   TENI-9156 (Ref con guion)
            match_row = re.search(r'(\d{1,3}\.\d{3}\.\d{3}-[\w\d])\s+(.+?)\s+([A-Za-z0-9\-]+)$', line.strip())
            if match_row:
                datos['nit'] = match_row.group(1)
                datos['nombre'] = match_row.group(2).strip()
                datos['ref_factura'] = match_row.group(3)
                break # Tomamos la primera coincidencia válida

        # Validación básica
        if not datos['fecha'] or not datos['nombre']:
            raise ValueError("No se pudieron extraer fecha o nombre del proveedor localmente.")

        return datos

    except subprocess.CalledProcessError:
        raise Exception("Error ejecutando pdftotext. Asegúrate de tener poppler-utils instalado.")
    except Exception as e:
        raise Exception(f"Error analizando PDF localmente: {e}")

def extraer_datos_egreso_hibrido(ruta_archivo):
    """Intenta IA primero, si falla, usa Local."""
    try:
        return extraer_datos_egreso_ia(ruta_archivo)
    except Exception as e:
        print(f"[!] IA Error: {e}")
        print(f"[!] Cambiando a método LOCAL...")
        return extraer_datos_egreso_local(ruta_archivo)

import sys

def organizar_agente():
    # --- Lógica de Reintento ---
    if "--reintentar" in sys.argv:
        print("[*] Modo Reintento activado.")
        carpeta_pendientes = os.path.join(BASE_OUTPUT, "_Pendientes")
        if os.path.exists(carpeta_pendientes):
            archivos_pendientes = os.listdir(carpeta_pendientes)
            if archivos_pendientes:
                print(f"[+] Moviendo {len(archivos_pendientes)} archivos de _Pendientes a input...")
                for f in archivos_pendientes:
                    shutil.move(os.path.join(carpeta_pendientes, f), os.path.join(WATCH_FOLDER, f))
            else:
                print("[-] No hay archivos en _Pendientes para reintentar.")
        else:
            print("[-] No existe la carpeta _Pendientes.")

        # Reintentar también Excepciones
        carpeta_excepciones = os.path.join(BASE_OUTPUT, "_Excepciones")
        if os.path.exists(carpeta_excepciones):
            archivos_excepciones = os.listdir(carpeta_excepciones)
            if archivos_excepciones:
                print(f"[+] Moviendo {len(archivos_excepciones)} archivos de _Excepciones a input...")
                for f in archivos_excepciones:
                    shutil.move(os.path.join(carpeta_excepciones, f), os.path.join(WATCH_FOLDER, f))
            else:
                print("[-] No hay archivos en _Excepciones para reintentar.")
        else:
            print("[-] No existe la carpeta _Excepciones.")

    archivos = [f for f in os.listdir(WATCH_FOLDER) if os.path.isfile(os.path.join(WATCH_FOLDER, f))]
    grupos_por_id = {}
    egresos_huerfanos = []

    # --- FASE 1: Clasificación Inicial (Python) ---
    for f in archivos:
        match = re.match(FILE_PATTERN, f)
        if match:
            id_lote = match.group(1)
            if id_lote not in grupos_por_id: grupos_por_id[id_lote] = []
            grupos_por_id[id_lote].append(f)
        else:
            egresos_huerfanos.append(f)

    # Helper para normalizar texto (quitar S.A.S, espacios, minusculas, tildes)
    def normalizar_texto(texto):
        if not texto: return ""
        import unicodedata
        texto = texto.lower()
        texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn') # Quitar tildes
        texto = re.sub(r'[^\w\s]', '', texto) # Quitar puntuacion
        texto = texto.replace("sas", "").replace("s a s", "").strip()
        return texto

    # --- FASE 2 & 3: Inteligencia y Organización Híbrida ---
    for archivo_egreso in egresos_huerfanos:
        ruta_completa = os.path.join(WATCH_FOLDER, archivo_egreso)
        try:
            print(f"--- Procesando: {archivo_egreso} ---")
            datos = extraer_datos_egreso_hibrido(ruta_completa)
            print(f"    Datos extraídos: {datos}")
            
            # Determinar carpeta de destino: /Contabilidad_{año}/{Cliente}-{mes}/
            # Formato fecha esperado YYYY-MM-DD
            try:
                fecha_dt = datetime.strptime(datos['fecha'], "%Y-%m-%d")
            except ValueError:
                # Intento de fallback si la fecha viene en otro formato (poco probable si es JSON de IA o Regex fijo)
                fecha_dt = datetime.now() 
            
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            
            nombre_mes = meses[fecha_dt.month - 1]
            carpeta_final = os.path.join(BASE_OUTPUT, f"Contabilidad_{fecha_dt.year}", f"{datos['cliente']}-{nombre_mes}")
            
            # Mover la Factura y Pago asociados (buscando por CONTENIDO: Nombre del Proveedor)
            nombre_proveedor_norm = normalizar_texto(datos.get('nombre', ''))
            
            grupo_encontrado = None
            archivos_grupo = []

            if nombre_proveedor_norm:
                for id_lote, docs in list(grupos_por_id.items()):
                    coincide = False
                    for doc in docs:
                        match = re.match(FILE_PATTERN, doc)
                        if match:
                            descripcion_doc = match.group(3)
                            desc_norm = normalizar_texto(descripcion_doc)
                            
                            # Matching difuso con thefuzz
                            ratio = fuzz.partial_ratio(desc_norm, nombre_proveedor_norm)
                            
                            # Umbral de similitud
                            if ratio > 80:
                                coincide = True
                                print(f"    [MATCH] '{descripcion_doc}' vs '{datos.get('nombre')}' (Ratio: {ratio}%)")
                                break
                    
                    if coincide:
                        grupo_encontrado = id_lote
                        archivos_grupo = docs
                        break # Solo necesitamos un grupo
            
            if grupo_encontrado:
                print(f"[+] Vinculando Grupo ID {grupo_encontrado} con {archivo_egreso}")
                
                # Crear carpeta si no existe
                os.makedirs(carpeta_final, exist_ok=True)

                # Mover el Egreso
                shutil.move(ruta_completa, os.path.join(carpeta_final, archivo_egreso))

                # Mover archivos del grupo
                for doc in archivos_grupo:
                    ruta_origen = os.path.join(WATCH_FOLDER, doc)
                    if os.path.exists(ruta_origen):
                        shutil.move(ruta_origen, os.path.join(carpeta_final, doc))
                
                del grupos_por_id[grupo_encontrado]
                print(f"[✓] Tríada organizada en: {carpeta_final}\n")
            else:
                # Si no se encontró grupo, mover a _Pendientes
                print(f"[-] No se encontraron soportes para {archivo_egreso}. Moviendo a _Pendientes.")
                carpeta_pendientes = os.path.join(BASE_OUTPUT, "_Pendientes")
                os.makedirs(carpeta_pendientes, exist_ok=True)
                shutil.move(ruta_completa, os.path.join(carpeta_pendientes, archivo_egreso))
                print(f" -> Movido a: {carpeta_pendientes}\n")
        
        except Exception as e:
            print(f"[!] Error procesando {archivo_egreso}: {e}")
            carpeta_excepciones = os.path.join(BASE_OUTPUT, "_Excepciones")
            os.makedirs(carpeta_excepciones, exist_ok=True)
            if os.path.exists(ruta_completa):
                shutil.move(ruta_completa, os.path.join(carpeta_excepciones, archivo_egreso)) 
            print(f" -> Movido a: {carpeta_excepciones}\n")

if __name__ == "__main__":
    organizar_agente()