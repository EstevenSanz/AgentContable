import os
import re
import shutil
import json
import google.genai as genai
from datetime import datetime
from thefuzz import fuzz
from dotenv import load_dotenv
import sys
import unicodedata

# --- NUEVOS IMPORTS ---
# Usamos tus scripts para extraer correctamente
from img_json import extract_text_from_image
from pdf_json import extract_text_from_pdf

load_dotenv()

# --- CONFIGURACIÓN DE MÚLTIPLES API KEYS ---
posibles_keys = [os.getenv("GOOGLE_API_KEY"), os.getenv("GOOGLE_API_KEY1")]
api_keys = [k for k in posibles_keys if k and k.strip()]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER_EGRESOS = os.path.join(BASE_DIR, "input", "EGRESOS")
FOLDER_RECIBOS = os.path.join(BASE_DIR, "input", "RECIBOS")
DATA_FOLDER = os.path.join(BASE_DIR, "Data")
BASE_OUTPUT = os.path.join(BASE_DIR, "output")

def comprobar_relacion_ia(datos_principal, texto_soporte, nombre_soporte):
    """Consulta a la IA (Gemini) usando pool de Keys para saber si un texto ruidoso de soporte pertenece a la transacción principal."""
    if not texto_soporte.strip() and not nombre_soporte.strip():
        return False
        
    print(f"      [*] Consultando a Gemini para relacionar soporte '{nombre_soporte}'...")
    
    nit = datos_principal.get('nit', 'Desconocido')
    plantilla = datos_principal.get('plantilla', 'Desconocido')
    nombre = datos_principal.get('nombre', 'Desconocido')
    doc_ref = datos_principal.get('documento_ref', 'Desconocido')
    fecha = datos_principal.get('fecha', 'Desconocido')
    monto = datos_principal.get('monto', 0.0)
    
    contents = f"""<system>
Task: Document Matching
Input: 
  - <ledger>: Accounting transaction metrics.
  - <support_filename>: The filename of the support document. (Crucial metric: often contains the payee's name or transaction ID).
  - <support_ocr>: Raw OCR text from an invoice, receipt, or transfer capture.
Rules:
  1. Evaluate if <support_ocr> or <support_filename> functionally validates/belongs to <ledger>.
  2. Tolerate minor OCR string noise (e.g. '1' via 'l').
  3. Search for intersecting amounts, dates, names (especially in <support_filename>), NIT/IDs, or references.
Output format: ONLY "SI" or "NO"
</system>

<ledger>
  <nit>{nit}</nit>
  <plantilla>{plantilla}</plantilla>
  <name>{nombre}</name>
  <doc_ref>{doc_ref}</doc_ref>
  <date>{fecha}</date>
  <amount>{monto}</amount>
</ledger>

<support_filename>
{nombre_soporte}
</support_filename>

<support_ocr>
{texto_soporte}
</support_ocr>

<result>"""
    
    ultimo_error = None
    for idx, key in enumerate(api_keys):
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents
            )
            respuesta = str(response.text).strip().upper()
            return "SI" in respuesta
        except Exception as e:
            ultimo_error = e
            print(f"      [!] API Key #{idx + 1} falló en relación ('{e}'). Intentando otra si existe...")
            
    raise Exception(f"Todas las API Keys fallaron relacionando {nombre_soporte}: {ultimo_error}")

def extraer_datos_documento_ia(ruta_archivo):
    print(f"[*] Intentando extracción con Gemini IA al archivo Principal...")
    contents = """<system>
Task: Structured Information Extraction from Accounting Image/PDF.
Rules:
  1. Detect document type context: "Egreso" (Expense) or "Recibo" (Income).
  2. Extract parameters into strictly formatted JSON.
  3. Return ONLY valid JSON, NO markdown wrapping (no ```json).
</system>

<schema_target>
{
  "tipo": "Egreso|Recibo",
  "nit": "string (123.456.789-0)",
  "nombre": "string (Third-party supplier/entity)",
  "cliente": "string (Company from the document header)",
  "monto": float (Egreso=Debitos, Recibo=Creditos),
  "documento_ref": "string (Document No.)",
  "fecha": "string (YYYY-MM-DD)"
}
</schema_target>"""
    ultimo_error = None
    for idx, key in enumerate(api_keys):
        try:
            client = genai.Client(api_key=key)
            imagen_o_pdf = client.files.upload(file=ruta_archivo)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[contents, imagen_o_pdf],
                config=genai.types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(response.text)
        except Exception as e:
            ultimo_error = e
            print(f"      [!] API Key #{idx + 1} falló en extracción principal ('{e}'). Intentando otra si existe...")
            
    raise Exception(f"Fallo Gemini IA con todas las keys: {ultimo_error}")

def normalizar_texto(texto):
    if not texto: return ""
    texto = str(texto).lower()
    texto = re.sub(r'\s+s\.?a\.?s\.?$', '', texto)
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = re.sub(r'[^\w\s]', '', texto)
    return texto.strip()

def regex_nit(texto):
    if not texto: return None
    match = re.search(r'(\d{1,3}\.?\d{3}\.?\d{3})', texto)
    if match:
        return match.group(1).replace(".", "")
    return None

def extraer_datos_documento_local(ruta_archivo, texto):
    print(f"[*] Intentando extracción LOCAL (Regex) de archivo Principal...")
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

        if lines:
            datos['cliente'] = lines[0].split("NIT:")[0].strip()

        fecha_match = re.search(r'(\d{2})\s+(\d{2})\s+(\d{4})', texto)
        if fecha_match:
            dia, mes, anio = fecha_match.groups()
            datos['fecha'] = f"{anio}-{mes}-{dia}"

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
        raise Exception(f"Error analizando localmente: {e}")

def extraer_datos_hibrido(ruta_archivo, texto):
    try:
        return extraer_datos_documento_ia(ruta_archivo)
    except Exception as e:
        print(f"[!] IA Error Extracción Principal: {e}")
        print(f"[!] Cambiando a método LOCAL para archivo principal...")
        return extraer_datos_documento_local(ruta_archivo, texto)


def organizar_agente():
    principales = []
    folders_to_scan = [FOLDER_EGRESOS, FOLDER_RECIBOS]
    
    if "--reintentar" in sys.argv:
        exc_path = os.path.join(BASE_OUTPUT, "_Excepciones")
        if os.path.exists(exc_path):
            print("[*] Modo REINTENTO activo...")
            folders_to_scan.append(exc_path)

    for folder in folders_to_scan:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if f.lower().endswith('.pdf'):
                    principales.append((os.path.join(folder, f), folder))

    # Extracción de Soportes usando nuestros métodos pdf_json e img_json
    soportes = []
    textos_soportes = {}
    if os.path.exists(DATA_FOLDER):
        for f in os.listdir(DATA_FOLDER):
            if f.lower().endswith(('.pdf', '.jpeg', '.jpg', '.png')):
                ruta = os.path.join(DATA_FOLDER, f)
                soportes.append(f)
                try:
                    if f.lower().endswith('.pdf'):
                        textos_soportes[f] = extract_text_from_pdf(ruta)
                    else:
                        textos_soportes[f] = extract_text_from_image(ruta)
                except Exception as e:
                    print(f" [!] Error al extraer texto de soporte {f}: {e}")
                    textos_soportes[f] = ""

    print(f"[*] {len(principales)} Principales encontrados, {len(soportes)} Soportes extraídos en /Data.")

    for ruta_principal, folder_origen in principales:
        archivo_nombre = os.path.basename(ruta_principal)
        try:
            print(f"\n--- Procesando Principal: {archivo_nombre} ---")
            # Extraemos texto principal usando tu nuevo sistema pdf_json (es más robusto)
            texto_p = extract_text_from_pdf(ruta_principal)
            
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
            
            # Parametros para la busqueda
            nit_busqueda = regex_nit(datos.get('nit', ''))
            doc_busqueda = normalizar_texto(datos.get('documento_ref', ''))
            nombre_busqueda = normalizar_texto(datos.get('nombre', ''))
            
            # Limpieza exhaustiva del monto extraído para match exacto
            monto_bruto = datos.get('monto')
            monto_busqueda = ""
            if monto_bruto:
                # Quitamos puntos decimales al monto y lo convertimos a string (Ej. 134594.0 -> 134594)
                monto_busqueda = str(int(float(monto_bruto)))
            
            print(f"    Buscando soportes ({len(soportes)} disp.) para '{folder_nombre}'...")
            
            # --- NUEVA LÓGICA DE EMPAREJAMIENTO HÍBRIDO ---
            for soporte in list(soportes):
                texto_sop = textos_soportes[soporte]
                coincide = False
                
                texto_sop_plano_numeros = texto_sop.replace(".", "").replace(",", "").replace("$", "").replace(" ", "")
                
                # Nivel 1: Exacto Híbrido y Nombre de Archivo
                if nit_busqueda and len(nit_busqueda) > 3 and nit_busqueda in texto_sop_plano_numeros:
                    print(f"      [MATCH] Exacto por NIT en el texto del soporte '{soporte}'")
                    coincide = True
                elif doc_busqueda and len(doc_busqueda) > 3 and doc_busqueda in normalizar_texto(texto_sop):
                    print(f"      [MATCH] Exacto por Doc. Ref en el texto del soporte '{soporte}'")
                    coincide = True
                elif nombre_busqueda and len(nombre_busqueda) > 3 and fuzz.partial_ratio(nombre_busqueda, normalizar_texto(soporte)) >= 85:
                    print(f"      [MATCH] Nombre de contacto '{datos.get('nombre')}' aparece detectado directamente en el nombre del archivo '{soporte}'")
                    coincide = True
                elif monto_busqueda and len(monto_busqueda) >= 4 and monto_busqueda in texto_sop_plano_numeros:
                    print(f"      [MATCH] Monto exacto '{monto_busqueda}' detectado en el texto extraído del soporte '{soporte}'")
                    coincide = True
                
                # Nivel 2: IA (Tratar de buscar con IA si falló exacto)
                if not coincide:
                    try:
                        resp_ia = comprobar_relacion_ia(datos, texto_sop, soporte)
                        if resp_ia:
                            print(f"      [MATCH] Aprobado por IA (Gemini) en '{soporte}'")
                            coincide = True
                    except Exception as e:
                        print(f"      [*] Fallo crítico Multi-Key en Inteligencia Artificial: Pasando a Fuzzy matching de repuesto...")
                        # Nivel 3. Fuzzy Match (Fallback por error en APIs)
                        fuzz_nit = fuzz.partial_ratio(nit_busqueda, texto_sop_plano_numeros) if nit_busqueda else 0
                        fuzz_doc = fuzz.partial_ratio(doc_busqueda, normalizar_texto(texto_sop)) if doc_busqueda and len(doc_busqueda) > 3 else 0
                        fuzz_monto = fuzz.partial_ratio(monto_busqueda, texto_sop_plano_numeros) if monto_busqueda and len(monto_busqueda) >= 4 else 0
                        
                        if fuzz_nit >= 80:
                            print(f"      [MATCH] Fuzzy Matching por NIT (Score {fuzz_nit}%) en '{soporte}'")
                            coincide = True
                        elif fuzz_doc >= 80:
                            print(f"      [MATCH] Fuzzy Matching por Doc. Ref (Score {fuzz_doc}%) en '{soporte}'")
                            coincide = True
                        elif fuzz_monto >= 95:
                            print(f"      [MATCH] Sub-Segmento Fuzzy Matching de Monto (Score {fuzz_monto}%) en '{soporte}'")
                            coincide = True
                
                if coincide:
                    soportes_asociados.append(soporte)
                    soportes.remove(soporte)

            os.makedirs(carpeta_final, exist_ok=True)
            shutil.move(ruta_principal, os.path.join(carpeta_final, archivo_nombre))
            for s in soportes_asociados:
                shutil.move(os.path.join(DATA_FOLDER, s), os.path.join(carpeta_final, s))
            
            print(f"[✓] Organizado en: {carpeta_final}")
            
        except Exception as e:
            print(f"[!] Error procesando {archivo_nombre}: {e}")
            exc_path = os.path.join(folder_origen, "_Excepciones")
            os.makedirs(exc_path, exist_ok=True)
            shutil.move(ruta_principal, os.path.join(exc_path, archivo_nombre))

    if soportes:
        print(f"\n[*] Moviendo {len(soportes)} soportes no asociados a Data/_Pendientes...")
        pend_path = os.path.join(DATA_FOLDER, "_Pendientes")
        os.makedirs(pend_path, exist_ok=True)
        for s in list(soportes):
            try:
                shutil.move(os.path.join(DATA_FOLDER, s), os.path.join(pend_path, s))
                soportes.remove(s)
            except Exception as e:
                print(f" [!] No se pudo mover {s}: {e}")

if __name__ == "__main__":
    organizar_agente()
