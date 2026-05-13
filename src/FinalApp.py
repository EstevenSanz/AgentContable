import asyncio
from aiohttp import ClientSession
from utils.data_processor import process_data
import logging

# Configuración del registro de errores
logging.basicConfig(filename='../logs/app.log', level=logging.ERROR)

async def fetch_external_data(url):
    """Realiza una solicitud HTTP GET asíncrona a la URL especificada y devuelve los datos."""
    async with ClientSession() as session:
        try:
            async with session.get(url) as response:
                return await response.json()
        except Exception as e:
            logging.error(f"Error al obtener datos externos: {e}")
            return None

def verify_credentials(username, password):
    """Valida las credenciales del usuario y devuelve True si son correctas."""
    # Suponiendo que 'config' contiene la contraseña hash
    from utils.config import PASSWORD_HASH
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    
    try:
        if not bcrypt.checkpw(hashed_password, PASSWORD_HASH):
            raise ValueError("Contraseña incorrecta")
    except ValueError as e:
        logging.error(f"Error de autenticación: {e}")
        return False
    return True

def main():
    """Función principal que se ejecuta al iniciar el programa."""
    username = input("Ingrese su nombre de usuario: ")
    password = input("Ingrese su contraseña: ")

    if not verify_credentials(username, password):
        logging.error("Acceso denegado")
        return
    
    data_url = "https://api.example.com/data"
    
    loop = asyncio.get_event_loop()
    external_data = loop.run_until_complete(fetch_external_data(data_url))
    processed_data = process_data(external_data)
    
    if processed_data:
        print(f"Datos procesados: {processed_data}")
    else:
        logging.error("No se pudieron obtener o procesar los datos")

if __name__ == "__main__":
    main()