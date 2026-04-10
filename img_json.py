# Extraer texto de png,jpg,jpeg y convertir a json hacer condicional si es pdf llamar a la funcion extract_text_from_pdf de pdf_json.py

import cv2
import pytesseract
import json
import os
from pdf_json import extract_text_from_pdf

# Obtener la ruta del directorio actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Obtener la ruta del directorio de datos
DATA_DIR = os.path.join(BASE_DIR, 'Data')


# Obtener las rutas de las imágenes y PDFs
def get_img_paths():
    rutas = []
    for folder in [DATA_DIR]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith((".png", ".jpg", ".jpeg", ".pdf")):
                    rutas.append(os.path.join(folder, file))
    return rutas

# Extraer texto de la imagen
def extract_text_from_image(ruta):
    img = cv2.imread(ruta)
    if img is None:
        return ""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    texto = pytesseract.image_to_string(thresh, lang='spa')
    return texto

# Convertir texto a json
def convert_to_json(texto):
    return json.loads(texto)

# Ejecutar el script
if __name__ == "__main__":
    rutas = get_img_paths()
    for ruta in rutas:
        if ruta.endswith(".pdf"):
            texto = extract_text_from_pdf(ruta)
            print(f"--- Texto plano extraído del PDF (ruta: {ruta}) ---")
            print(texto)
            # Nota: Desactivado convert_to_json(texto) temporalmente porque
            # si el PDF no tiene formato JSON estricto {"clave": "valor"}
            # va a generar el error JSONDecodeError que vimos antes.
            # json_data = convert_to_json(texto)
            # print(json.dumps(json_data, indent=4))
        else:
            texto = extract_text_from_image(ruta)
            print(f"--- Texto plano extraído de la imagen (ruta: {ruta}) ---")
            print(texto)
            # Igual para la imagen, solo pasarlo a JSON si es JSON válido
            # json_data = convert_to_json(texto)
            # print(json.dumps(json_data, indent=4))