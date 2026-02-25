import os
import json

# Ruta absoluta a la carpeta input del proyecto
folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input")
extension_filter = '.pdf'

output = []

if os.path.exists(folder_path):
    for filename in os.listdir(folder_path):
        if extension_filter is None or filename.endswith(extension_filter):
            file_path = os.path.join(folder_path, filename)
            
            # Solo procesar si es un archivo
            if os.path.isfile(file_path):
                try:
                    output.append({
                        "name": filename,
                        "path": file_path,
                        "extension": os.path.splitext(filename)[1],
                        "size_bytes": os.path.getsize(file_path)
                    })
                except Exception as e:
                    output.append({
                        "name": filename,
                        "error": str(e)
                    })
else:
    output.append({"error": f"La ruta no existe: {folder_path}"})

# Imprimir el JSON resultante para que n8n u otro script pueda capturarlo
print(json.dumps(output))