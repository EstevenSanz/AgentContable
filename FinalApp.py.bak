import os
import re
import shutil
from datetime import datetime
import sys
import unicodedata

# pyrefly: ignore [missing-import]
# Scripts propios para extracción de texto
from extractor import extract_text
from parsearf import parsear_imagen
from parsear import parsear_principal
from matcher import nombre_match_basico
# pyrefly: ignore [missing-import]
from thefuzz import fuzz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER_EGRESOS = os.path.join(BASE_DIR, "input", "EGRESOS")
FOLDER_RECIBOS = os.path.join(BASE_DIR, "input", "RECIBOS")
DATA_FOLDER = os.path.join(BASE_DIR, "Data")
BASE_OUTPUT = os.path.join(BASE_DIR, "output")

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
    print(f"[*] Extracción LOCAL (Regex) de archivo Principal...")
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

    # Extracción de Soportes usando extractor unificado y parseo de metadata
    soportes = []
    imagenes_parseadas = []
    if os.path.exists(DATA_FOLDER):
        for f in os.listdir(DATA_FOLDER):
            if f.lower().endswith(('.pdf', '.jpeg', '.jpg', '.png')):
                ruta = os.path.join(DATA_FOLDER, f)
                soportes.append(f)
                try:
                    texto_sop = extract_text(ruta)
                    img_data = parsear_imagen(texto_sop, f)
                    img_data["texto_raw"] = texto_sop
                    imagenes_parseadas.append(img_data)
                except Exception as e:
                    print(f" [!] Error al extraer/parsear soporte {f}: {e}")

    print(f"[*] {len(principales)} Principales encontrados, {len(soportes)} Soportes extraídos y parseados en /Data.")

    for ruta_principal, folder_origen in principales:
        archivo_nombre = os.path.basename(ruta_principal)
        try:
            print(f"\n--- Procesando Principal: {archivo_nombre} ---")
            # Extraemos texto principal usando tu nuevo sistema unificado
            texto_p = extract_text(ruta_principal)
            
            datos = extraer_datos_documento_local(ruta_principal, texto_p)
            print(f"    Datos extraídos localmente: {datos}")
            
            # Integración: obtener registros detallados usando parsear_principal
            registros = parsear_principal(texto_p)
            
            # Si no se obtienen registros de la tabla, creamos un registro simulado con los datos locales
            if not registros:
                monto_val = 0.0
                if datos.get('nit'):
                    match_monto = re.search(r'([\d,]+\.\d{2})\s+' + re.escape(datos['nit']), texto_p)
                    if match_monto:
                        from parsear import limpiar_numero
                        try:
                            monto_val = limpiar_numero(match_monto.group(1))
                        except:
                            pass
                
                registros = [{
                    "nombre": datos.get('nombre', ''),
                    "nit": datos.get('nit', ''),
                    "documento_ref": datos.get('documento_ref', ''),
                    "debito": monto_val
                }]
                
            print(f"    Registros a procesar: {len(registros)}")
            
            try:
                fecha_dt = datetime.strptime(datos['fecha'], "%Y-%m-%d")
            except:
                fecha_dt = datetime.now()
            
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            nombre_mes = meses[fecha_dt.month - 1]
            
            folder_contabilidad = f"Contabilidad_{nombre_mes}_{fecha_dt.year}"
            folder_cliente = normalizar_texto(datos.get('cliente', 'Empresa')).capitalize()
            
            # Determinar el nombre de la carpeta (tomamos el del primer registro si existe)
            nombre_carpeta = datos.get('nombre', 'Tercero')
            if registros and registros[0].get('nombre'):
                nombre_carpeta = registros[0]['nombre']
            folder_nombre = normalizar_texto(nombre_carpeta).capitalize()
            
            carpeta_final = os.path.join(BASE_OUTPUT, folder_contabilidad, folder_cliente, folder_nombre)
            
            soportes_asociados = []
            print(f"    Buscando soportes ({len(soportes)} disp.) para la carpeta '{folder_nombre}'...")
            
            # --- LÓGICA DE EMPAREJAMIENTO COMBINADA (FinalApp + matcher) ---
            for registro in registros:
                mejor_soporte = None
                mejor_score = 0
                mejor_reasons = []
                
                nit_busqueda = regex_nit(registro.get('nit', datos.get('nit', '')))
                doc_busqueda = normalizar_texto(registro.get('documento_ref', datos.get('documento_ref', '')))
                nombre_busqueda = normalizar_texto(registro.get('nombre', ''))
                
                monto_busqueda = ""
                if registro.get('debito'):
                    monto_busqueda = str(int(float(registro.get('debito'))))
                    
                for img in [i for i in imagenes_parseadas if i["archivo"] in soportes]:
                    soporte = img["archivo"]
                    texto_sop = img["texto_raw"]
                    texto_sop_plano_numeros = texto_sop.replace(".", "").replace(",", "").replace("$", "").replace(" ", "")
                    
                    score = 0
                    match_reasons = []
                    
                    # 1. Match Exacto por NIT (Fuerte)
                    if nit_busqueda and len(nit_busqueda) > 3 and nit_busqueda in texto_sop_plano_numeros:
                        score += 100
                        match_reasons.append("Exacto por NIT")
                        
                    # 2. Match Exacto por Documento Ref
                    if doc_busqueda and len(doc_busqueda) > 3 and doc_busqueda in normalizar_texto(texto_sop):
                        score += 80
                        match_reasons.append("Exacto por Doc. Ref")
                        
                    # 3. Comparativo de Montos (del matcher.py)
                    valor_reg = registro.get("debito")
                    valor_img = img.get("mejor_valor")
                    if valor_img is not None and valor_reg is not None:
                        diff = abs(valor_img - valor_reg)
                        if diff < 5:
                            score += 80
                            match_reasons.append("Monto exacto (matcher)")
                        elif diff < 1000:
                            score += 50
                            match_reasons.append("Monto cercano (matcher)")
                        elif diff < 10000:
                            score += 20
                            match_reasons.append("Monto aproximado (matcher)")
                            
                    # 4. Monto exacto como texto (de FinalApp)
                    if monto_busqueda and len(monto_busqueda) >= 4 and monto_busqueda in texto_sop_plano_numeros:
                        score += 60
                        match_reasons.append("Monto exacto en texto")

                    # 5. Nombres en Archivo y Texto (del matcher.py)
                    if nombre_match_basico(registro.get("nombre", ""), img.get("nombre_archivo", "")):
                        score += 30
                        match_reasons.append("Nombre en archivo (matcher)")
                        
                    for n in img.get("nombres_texto", []):
                        if nombre_match_basico(registro.get("nombre", ""), n):
                            score += 10
                            match_reasons.append("Nombre en OCR (matcher)")
                            break
                            
                    # 6. Fuzzy Match (de FinalApp)
                    if not match_reasons: # Solo si no hay hits exactos
                        fuzz_nit = fuzz.partial_ratio(nit_busqueda, texto_sop_plano_numeros) if nit_busqueda else 0
                        fuzz_doc = fuzz.partial_ratio(doc_busqueda, normalizar_texto(texto_sop)) if doc_busqueda and len(doc_busqueda) > 3 else 0
                        if fuzz_nit >= 80:
                            score += 40
                            match_reasons.append(f"Fuzzy NIT ({fuzz_nit}%)")
                        if fuzz_doc >= 80:
                            score += 40
                            match_reasons.append(f"Fuzzy Doc ({fuzz_doc}%)")
                            
                    if score > mejor_score:
                        mejor_score = score
                        mejor_soporte = img
                        mejor_reasons = match_reasons

                if mejor_score >= 30 and mejor_soporte: # Umbral mínimo de confianza
                    print(f"      [MATCH COMBINADO] Soporte '{mejor_soporte['archivo']}' asociado a '{registro.get('nombre')}'. Score: {mejor_score}. Razones: {', '.join(mejor_reasons)}")
                    soportes_asociados.append(mejor_soporte["archivo"])
                    soportes.remove(mejor_soporte["archivo"])

            # Remover duplicados si varios registros cazaron el mismo soporte
            soportes_asociados = list(set(soportes_asociados))

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
