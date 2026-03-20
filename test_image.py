import pytesseract
import cv2 
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'Data')


def extract_text_from_image(ruta):
    img = cv2.imread(ruta)
    if img is None:
        return ""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    texto = pytesseract.image_to_string(thresh, lang='spa')
    return texto


