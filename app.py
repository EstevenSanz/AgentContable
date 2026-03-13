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

load_dotenv()

# --- CONFIGURACIÓN ---
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCH_FOLDER = os.path.join(BASE_DIR, "input")
BASE_OUTPUT = os.path.join(BASE_DIR, "output")

def extraer_datos_documento_ia(ruta_archivo):
    print(f"[*] Intentando extracción con Gemini IA...")
    contents = """
    Analiza este documento contable. Determina si es un "Egreso" o un "Recibo".
    Extrae:
    1. 'tipo': "Egreso" o "Recibo"
    2. 'nit': NIT (del tercero, ej. 901.359.144-2)
    3. 'nombre': Nombre del cliente/proveedor.
    4. 'documento_ref': DOCUMENTO de la tabla.
    5. 'descripcion': Descripción del encabezado o de la transacción.
    6. 'monto': Si es Egreso extrae DEBITOS, si es Recibo extrae CREDITOS.
    7. 'fecha': Fecha del comprobante (YYYY-MM-DD).

    Responde SOLAMENTE en JSON válido con estas claves:
    {"tipo": "...", "nit": "...", "nombre": "...", "monto": 0.0, "documento_ref": "...", "descripcion": "...", "fecha": "YYYY-MM-DD"}
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
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn') # Quitar tildes
    texto = re.sub(r'[^\w\s]', '', texto) # Quitar puntuacion
    texto = texto.replace("sas", "").replace("s a s", "").strip()
    return texto

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
        lines = texto.split('\n')
        datos = {
            "tipo": "Desconocido",
            "descripcion": None,
            "fecha": None,
            "nit": None,
            "nombre": None,
            "documento_ref": None,
            "monto": 0.0
        }

        texto_upper = texto.upper()
        if "COMPROBANTE DE EGRESO" in texto_upper or " COMPROBANTE DE EGRESO " in texto_upper:
            datos["tipo"] = "Egreso"
        elif "RECIBO DE CAJA" in texto_upper or "RECIBOS DE CAJA" in texto_upper:
            datos["tipo"] = "Recibo"

        # Fecha: DD MM YYYY
        fecha_match = re.search(r'(\d{2})\s+(\d{2})\s+(\d{4})', texto)
        if fecha_match:
            dia, mes, anio = fecha_match.groups()
            datos['fecha'] = f"{anio}-{mes}-{dia}"
        else:
            fecha_match_2 = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', texto)
            if fecha_match_2:
                anio, mes, dia = fecha_match_2.groups()
                datos['fecha'] = f"{anio}-{mes}-{dia}"

        # Datos de tabla
        for line in lines:
            match_row = re.search(r'(\d{1,3}\.\d{3}\.\d{3}-[\w\d])\s+(.+?)\s+([A-Za-z0-9\-]+)$', line.strip())
            if match_row:
                datos['nit'] = match_row.group(1)
                datos['nombre'] = match_row.group(2).strip()
                datos['documento_ref'] = match_row.group(3)
                
                desc_match = re.search(r'(\d{2}-\d{2}-\d{2}-?\d{0,2})\s+(.+?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', line.strip())
                if desc_match:
                    desc_posible = desc_match.group(2).strip()
                    if desc_posible and desc_posible != datos['nombre']:
                        datos['descripcion'] = desc_posible
                break
                
        # Fallback for Descripcion si no se encontro en linea
        if not datos['descripcion']:
            if lines:
                datos['descripcion'] = lines[0].strip()

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
    if "--reintentar" in sys.argv:
        print("[*] Modo Reintento activado.")
        for folder in ["_Pendientes", "_Excepciones"]:
            ruta = os.path.join(BASE_OUTPUT, folder)
            if os.path.exists(ruta):
                archivos = os.listdir(ruta)
                if archivos:
                    print(f"[+] Moviendo {len(archivos)} archivos de {folder} a input...")
                    for f in archivos:
                        shutil.move(os.path.join(ruta, f), os.path.join(WATCH_FOLDER, f))

    archivos = [f for f in os.listdir(WATCH_FOLDER) if os.path.isfile(os.path.join(WATCH_FOLDER, f)) and f.lower().endswith('.pdf')]
    documentos_principales = []
    documentos_soportes = []
    textos_pdfs = {}

    print("[*] Clasificando documentos...")
    for f in archivos:
        ruta_completa = os.path.join(WATCH_FOLDER, f)
        texto = obtener_texto_pdf(ruta_completa)
        textos_pdfs[f] = texto
        
        texto_upper = texto.upper()
        if "COMPROBANTE DE EGRESO" in texto_upper or "RECIBOS DE CAJA" in texto_upper or "RECIBO DE CAJA" in texto_upper:
            documentos_principales.append(f)
        else:
            documentos_soportes.append(f)

    print(f"[+] {len(documentos_principales)} Principales, {len(documentos_soportes)} Soportes.")

    for archivo_principal in documentos_principales:
        ruta_completa = os.path.join(WATCH_FOLDER, archivo_principal)
        try:
            print(f"\n--- Procesando Principal: {archivo_principal} ---")
            datos = extraer_datos_hibrido(ruta_completa, textos_pdfs[archivo_principal])
            print(f"    Datos extraídos: {datos}")
            
            try:
                fecha_dt = datetime.strptime(datos['fecha'], "%Y-%m-%d")
            except:
                fecha_dt = datetime.now()
            
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            nombre_mes = meses[fecha_dt.month - 1]
            
            # Formato Carpeta: /Contabilidad_{Mes}_{Año}/{Cliente}/{Nombre}+{ID}
            cliente_folder = normalizar_texto(datos.get('descripcion') or datos.get('nombre') or 'Desconocido').upper()
            nombre_proveedor = (datos.get('nombre') or 'Proveedor').replace("/", "-")
            doc_ref = datos.get('documento_ref') or 'SinRef'
            
            carpeta_final = os.path.join(BASE_OUTPUT, f"Contabilidad_{nombre_mes}_{fecha_dt.year}", cliente_folder, f"{nombre_proveedor}+{doc_ref}")
            
            soportes_asociados = []
            nit_busqueda = regex_nit(datos.get('nit', ''))
            doc_busqueda = normalizar_texto(datos.get('documento_ref', ''))
            
            print(f"    Buscando soportes con NIT: {nit_busqueda} o Documento: {doc_busqueda}...")
            for soporte in list(documentos_soportes):
                texto_soporte = textos_pdfs[soporte]
                texto_soporte_norm = normalizar_texto(texto_soporte)
                
                coincide = False
                if nit_busqueda and nit_busqueda in texto_soporte:
                    coincide = True
                    print(f"      [MATCH] '{soporte}' por NIT en el texto.")
                elif doc_busqueda and len(doc_busqueda) > 3 and doc_busqueda in texto_soporte_norm:
                    coincide = True
                    print(f"      [MATCH] '{soporte}' por Referencia de Documento en el texto.")
                    
                if coincide:
                    soportes_asociados.append(soporte)
                    documentos_soportes.remove(soporte)
            
            os.makedirs(carpeta_final, exist_ok=True)
            shutil.move(ruta_completa, os.path.join(carpeta_final, archivo_principal))
            for doc in soportes_asociados:
                ruta_soporte = os.path.join(WATCH_FOLDER, doc)
                if os.path.exists(ruta_soporte):
                    shutil.move(ruta_soporte, os.path.join(carpeta_final, doc))
            print(f"[✓] Documentos organizados en: {carpeta_final}")
            
        except Exception as e:
            print(f"[!] Error procesando {archivo_principal}: {e}")
            carpeta_excepciones = os.path.join(BASE_OUTPUT, "_Excepciones")
            os.makedirs(carpeta_excepciones, exist_ok=True)
            if os.path.exists(ruta_completa):
                shutil.move(ruta_completa, os.path.join(carpeta_excepciones, archivo_principal))

if __name__ == "__main__":
    organizar_agente()