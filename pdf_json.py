# Extraer texto de pdf y convertir a json

import pdfplumber
import json
import os

# Obtener la ruta del directorio actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Obtener la ruta del directorio de entrada
DATA_DIR = os.path.join(BASE_DIR, 'input')
# Obtener la ruta del directorio de egresos
DATA_DIR_EGRESOS = os.path.join(DATA_DIR, 'EGRESOS')
# Obtener la ruta del directorio de recibos
DATA_DIR_RECIBOS = os.path.join(DATA_DIR, 'RECIBOS')


# Obtener las rutas de los PDFs
def get_pdf_paths():
    rutas = []
    for folder in [DATA_DIR_EGRESOS, DATA_DIR_RECIBOS]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(".pdf"):
                    rutas.append(os.path.join(folder, file))
    return rutas

# Extraer texto del PDF
def extract_text_from_pdf(ruta):
    with pdfplumber.open(ruta) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += page.extract_text()
    return texto

# Convertir texto a json
def convert_to_json(texto):
    return json.loads(texto)

# Ejecutar el script
if __name__ == "__main__":
    rutas = get_pdf_paths()
    for ruta in rutas:
        texto = extract_text_from_pdf(ruta)
        json_data = convert_to_json(texto)
        print(f"--- Datos del PDF: {ruta} ---")
        print(json.dumps(json_data, indent=4))