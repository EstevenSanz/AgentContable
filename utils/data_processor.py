from .config import MAX_BATCH_SIZE

def process_data(data):
    """Procesa los datos recibidos y devuelve el resultado."""
    # Lógica optimizada para procesar datos
    
    if not data:
        logging.error("Datos vacíos o no proporcionados")
        return None
    
    processed = []
    
    for batch in range(0, len(data), MAX_BATCH_SIZE):
        chunk = data[batch:batch + MAX_BATCH_SIZE]
        # Procesamiento de cada fragmento
        pass
    
    return processed