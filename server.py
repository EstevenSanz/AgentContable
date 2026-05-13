import sys
import io
# pyrefly: ignore [missing-import]
from flask import Flask, jsonify, send_from_directory
from newApp import organizar_agente

app = Flask(__name__, static_folder='static')


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/ejecutar', methods=['POST'])
def ejecutar():
    """Ejecuta el procesamiento completo de documentos contables."""
    # Capturar la salida de consola del proceso
    captura = io.StringIO()
    stdout_original = sys.stdout
    sys.stdout = captura

    try:
        organizar_agente()
        sys.stdout = stdout_original
        log = captura.getvalue()
        return jsonify({
            'status': 'ok',
            'mensaje': 'Procesamiento completado exitosamente.',
            'log': log
        })
    except Exception as e:
        sys.stdout = stdout_original
        log = captura.getvalue()
        return jsonify({
            'status': 'error',
            'mensaje': f'Error durante el procesamiento: {e}',
            'log': log
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
