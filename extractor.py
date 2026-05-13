# pyrefly: ignore [missing-import]
import os
# pyrefly: ignore [missing-import]
from pdf import extraer_texto_pdf
# pyrefly: ignore [missing-import]
from ocr import extraer_texto_imagen

def extract_text(path:str) -> str:

    extension = os.path.splitext(path)[1].lower()

    if extension == ".pdf":
        return extraer_texto_pdf(path)

    if extension in [".jpg",".jpeg",".png"]:
        return extraer_texto_imagen(path)
        
    else:       
        print(f"[WARNING] Tipo no soportado: {path}")
        return ""

    
    