# pyrefly: ignore [missing-import]
import easyocr
import warnings

# Ignorar los warnings inofensivos de PyTorch sobre 'pin_memory' al usar CPU
warnings.filterwarnings("ignore", category=UserWarning, module="torch\\.utils\\.data\\.dataloader")

#LEER IMAGENES
reader = easyocr.Reader(['es'], gpu=False)

def extraer_texto_imagen(path: str) -> str:
    """
    Extrae texto desde imagen usando OCR
    """
    try:
        result = reader.readtext(path, detail=0)
        return " ".join(result)

    except Exception as e:
        print(f"[ERROR] OCR: {path} → {e}")
        return ""