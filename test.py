from pdf_json import extract_text_from_pdf, get_pdf_paths
from img_json import extract_text_from_image, get_img_paths

print("===== PROCESANDO TODOS LOS PDFS =====")
for ruta_pdf in get_pdf_paths():
    print(f"\n--- PDF: {ruta_pdf} ---")
    print(extract_text_from_pdf(ruta_pdf))

print("\n===== PROCESANDO TODAS LAS IMÁGENES =====")
for ruta_img in get_img_paths():
    print(f"\n--- Imagen: {ruta_img} ---")
    print(extract_text_from_image(ruta_img))