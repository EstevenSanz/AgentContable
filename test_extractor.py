import os
import json
import google.genai as genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def extract(ruta_archivo):
    contents = """
    Analiza este documento contable (puede ser Comprobante de Egreso o Recibo de Caja o un soporte).
    Determina si es un documento principal ("Egreso" o "Recibo") o no.
    Si es principal, extrae de la tabla principal:
    1. 'tipo': "Egreso" o "Recibo"
    2. 'nit': NIT (del tercero, ej. 901.359.144-2)
    3. 'nombre': Nombre del cliente/proveedor (ej. TANGIBLE PAQUETE CO)
    4. 'documento_ref': DOCUMENTO de la tabla (ej. 000000558)
    5. 'descripcion': DESCRIPCION de la transacción (ej. PAULA CALDAS AUN SI)
    6. 'monto': Si es Egreso extrae el valor de DEBITOS, si es Recibo extrae el valor de CREDITOS (Solo el número como flotante).
    7. 'fecha': Fecha del comprobante (YYYY-MM-DD)

    Responde SOLAMENTE en JSON válido con estas claves:
    {"es_principal": true/false, "tipo": "...", "nit": "...", "nombre": "...", "monto": 0.0, "documento_ref": "...", "descripcion": "...", "fecha": "YYYY-MM-DD"}
    """
    imagen_o_pdf = client.files.upload(file=ruta_archivo)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[contents, imagen_o_pdf],
        config=genai.types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(response.text)

print("558:", extract("input/00001 000000558 20260209.pdf"))
print("559:", extract("input/00001 000000559 20260213.pdf"))
