# pyrefly: ignore [missing-import]
import pdfplumber

#LEER PDF
def extraer_texto_pdf(path:str) -> str:

    text=""

    try:
        with pdfplumber.open(path) as pdf:

            for page in pdf.pages:
                contenido=page.extract_text()
                if contenido:
                    text+=contenido+"\n"

                    
    except Exception as e:
        print(f"[ERROR] PDF: {path} -> {e}")

    return text