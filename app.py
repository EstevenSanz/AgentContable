import os
import re
import shutil
import subprocess
import json
import google.genai as genai
from datetime import datetime
from thefuzz import fuzz
from dotenv import load_dotenv
import sys
import unicodedata
from test_image import extract_text_from_image

load_dotenv()

# --- CONFIGURACIÓN ---
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ahora los principales están en subcarpetas de input/
FOLDER_EGRESOS = os.path.join(BASE_DIR, "input", "EGRESOS")
FOLDER_RECIBOS = os.path.join(BASE_DIR, "input", "RECIBOS")
# Los soportes siguen en Data/
DATA_FOLDER = os.path.join(BASE_DIR, "Data")
BASE_OUTPUT = os.path.join(BASE_DIR, "output")

def extraer_datos_documento_ia(ruta_archivo):
    print(f"[*] Intentando extracción con Gemini IA...")
    contents = """
    Analiza este documento contable. Determina si es un "Egreso" o un "Recibo".
    Extrae:
    1. 'tipo': "Egreso" o "Recibo"
    2. 'nit': NIT del Tercero (ej. 901.359.144-2)
    3. 'nombre': Nombre del proveedor o tercero (ej. Blondatex, Francesca Mendoza).
    4. 'cliente': Nombre de la empresa dueña del documento (encabezado, ej: 'Tangible').
    5. 'documento_ref': Número de DOCUMENTO de la tabla.
    6. 'monto': Si es Egreso extrae DEBITOS, si es Recibo extrae CREDITOS.
    7. 'fecha': Fecha del comprobante (YYYY-MM-DD).

    Responde SOLAMENTE en JSON válido con estas claves:
    {"tipo": "...", "nit": "...", "nombre": "...", "cliente": "...", "monto": 0.0, "documento_ref": "...", "fecha": "YYYY-MM-DD"}
    """
    try:
        imagen_o_pdf = client.files.upload(file=ruta_archivo)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[contents, imagen_o_pdf],
            config=genai.types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        raise Exception(f"Fallo Gemini IA: {e}")

def normalizar_texto(texto):
    if not texto: return ""
    texto = str(texto).lower()
    # Eliminar S.A.S, SAS, S A S al final para nombres de carpetas más limpios
    texto = re.sub(r'\s+s\.?a\.?s\.?$', '', texto)
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn') # Quitar tildes
    texto = re.sub(r'[^\w\s]', '', texto) # Quitar puntuacion
    return texto.strip()

def regex_nit(texto):
    if not texto: return None
    match = re.search(r'(\d{1,3}\.?\d{3}\.?\d{3})', texto)
    if match:
        nit_str = match.group(1).replace(".", "")
        return nit_str
    return None

def extraer_datos_documento_local(ruta_archivo, texto):
    print(f"[*] Intentando extracción LOCAL (Regex)...")
    try:
        lines = [l.strip() for l in texto.split('\n') if l.strip()]
        datos = {
            "tipo": "Desconocido",
            "cliente": "Empresa",
            "fecha": None,
            "nit": None,
            "nombre": None,
            "documento_ref": None,
            "monto": 0.0
        }

        texto_upper = texto.upper()
        if "COMPROBANTE DE EGRESO" in texto_upper:
            datos["tipo"] = "Egreso"
        elif "RECIBO DE CAJA" in texto_upper or "RECIBOS DE CAJA" in texto_upper:
            datos["tipo"] = "Recibo"

        # Cliente: Generalmente la primera línea con texto
        if lines:
            datos['cliente'] = lines[0].split("NIT:")[0].strip()
        
        # Refinar cliente si se detecta Tangible o su NIT
        if "901359144" in texto or "TANGIBLE" in texto_upper:
            datos['cliente'] = "Tangible"

        # Fecha: DD MM YYYY
        fecha_match = re.search(r'(\d{2})\s+(\d{2})\s+(\d{4})', texto)
        if fecha_match:
            dia, mes, anio = fecha_match.groups()
            datos['fecha'] = f"{anio}-{mes}-{dia}"

        # Datos de tabla
        for line in lines:
            match_row = re.search(r'(\d{1,3}\.\d{3}\.\d{3}-[\w\d])\s+(.+?)\s+([A-Za-z0-9\-]+)$', line)
            if match_row:
                datos['nit'] = match_row.group(1)
                datos['nombre'] = match_row.group(2).strip()
                datos['documento_ref'] = match_row.group(3)
                break

        if not datos['fecha'] or not datos['nit']:
            raise ValueError("No se pudo extraer información clave localmente.")

        return datos
    except Exception as e:
        raise Exception(f"Error analizando PDF localmente: {e}")

def extraer_datos_hibrido(ruta_archivo, texto):
    try:
        return extraer_datos_documento_ia(ruta_archivo)
    except Exception as e:
        print(f"[!] IA Error: {e}")
        print(f"[!] Cambiando a método LOCAL...")
        return extraer_datos_documento_local(ruta_archivo, texto)

def obtener_texto_pdf(ruta_archivo):
    try:
        result = subprocess.run(['pdftotext', '-layout', ruta_archivo, '-'], capture_output=True, text=True, check=True)
        return result.stdout
    except Exception:
        return ""

def organizar_agente():
    # Escanear principales en sus respectivas carpetas
    principales = [] # Lista de tuplas (ruta_completa, carpeta_origen)
    folders_to_scan = [FOLDER_EGRESOS, FOLDER_RECIBOS]
    
    # Si se pasa el argumento --reintentar, también escaneamos las excepciones previas
    if "--reintentar" in sys.argv:
        exc_path = os.path.join(BASE_OUTPUT, "_Excepciones")
        if os.path.exists(exc_path):
            print("[*] Modo REINTENTO activo: Escaneando carpeta de excepciones...")
            folders_to_scan.append(exc_path)

    for folder in folders_to_scan:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if f.lower().endswith('.pdf'):
                    principales.append((os.path.join(folder, f), folder))

    # Escanear soportes en Data
    soportes = []
    textos_soportes = {}
    if os.path.exists(DATA_FOLDER):
        for f in os.listdir(DATA_FOLDER):
            if f.lower().endswith('.pdf') or f.lower().endswith('.jpeg') or f.lower().endswith('.jpg') or f.lower().endswith('.png'):
                ruta = os.path.join(DATA_FOLDER, f)
                soportes.append(f)
                if f.lower().endswith('.pdf'):
                    textos_soportes[f] = obtener_texto_pdf(ruta)
                else:
                    textos_soportes[f] = extract_text_from_image(ruta)

    print(f"[*] {len(principales)} Principales encontrados, {len(soportes)} Soportes en Data.")

    for ruta_principal, folder_origen in principales:
        archivo_nombre = os.path.basename(ruta_principal)
        try:
            print(f"\n--- Procesando Principal: {archivo_nombre} ---")
            texto_p = obtener_texto_pdf(ruta_principal)
            datos = extraer_datos_hibrido(ruta_principal, texto_p)
            print(f"    Datos extraídos: {datos}")
            
            try:
                fecha_dt = datetime.strptime(datos['fecha'], "%Y-%m-%d")
            except:
                fecha_dt = datetime.now()
            
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            nombre_mes = meses[fecha_dt.month - 1]
            
            folder_contabilidad = f"Contabilidad_{nombre_mes}_{fecha_dt.year}"
            folder_cliente = normalizar_texto(datos.get('cliente', 'Empresa')).capitalize()
            folder_nombre = normalizar_texto(datos.get('nombre', 'Tercero')).capitalize()
            
            carpeta_final = os.path.join(BASE_OUTPUT, folder_contabilidad, folder_cliente, folder_nombre)
            
            soportes_asociados = []
            nit_busqueda = regex_nit(datos.get('nit', ''))
            doc_busqueda = normalizar_texto(datos.get('documento_ref', ''))
            
            print(f"    Buscando soportes para '{folder_nombre}' (NIT: {nit_busqueda})...")
            
            # Busqueda de soportes
            for soporte in list(soportes):
                texto_sop = textos_soportes[soporte]
                
                coincide = False
                if nit_busqueda and nit_busqueda in texto_sop.replace(".", ""):
                    coincide = True
                elif doc_busqueda and len(doc_busqueda) > 3 and doc_busqueda in normalizar_texto(texto_sop):
                    coincide = True
                
                if coincide:
                    print(f"      [MATCH] Soporte: {soporte}")
                    soportes_asociados.append(soporte)
                    soportes.remove(soporte)

            os.makedirs(carpeta_final, exist_ok=True)
            shutil.move(ruta_principal, os.path.join(carpeta_final, archivo_nombre))
            for s in soportes_asociados:
                shutil.move(os.path.join(DATA_FOLDER, s), os.path.join(carpeta_final, s))
            
            print(f"[✓] Organizado en: {carpeta_final}")
            
        except Exception as e:
            print(f"[!] Error en {archivo_nombre}: {e}")
            # Opción 2: Mover a subcarpeta del origen
            exc_path = os.path.join(folder_origen, "_Excepciones")
            os.makedirs(exc_path, exist_ok=True)
            shutil.move(ruta_principal, os.path.join(exc_path, archivo_nombre))

    # Al final, mover lo que quedó en Data a subcarpeta local _Pendientes
    if soportes:
        print(f"\n[*] Moviendo {len(soportes)} soportes no asociados a Data/_Pendientes...")
        pend_path = os.path.join(DATA_FOLDER, "_Pendientes")
        os.makedirs(pend_path, exist_ok=True)
        for s in soportes:
            try:
                shutil.move(os.path.join(DATA_FOLDER, s), os.path.join(pend_path, s))
            except Exception as e:
                print(f" [!] No se pudo mover {s}: {e}")

if __name__ == "__main__":
    organizar_agente()