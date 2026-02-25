import sys
import os

# Set the path to the current directory to ensure reliable imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

import app

if __name__ == "__main__":
    # Simular el argumento --reintentar para que app.py active el modo reintento
    if "--reintentar" not in sys.argv:
        sys.argv.append("--reintentar")
    
    print("[*] Iniciando wrapper de reintento...")
    app.organizar_agente()
