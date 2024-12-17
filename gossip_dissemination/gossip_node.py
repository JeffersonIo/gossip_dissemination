import json
import random
import time
from flask import Flask, request, jsonify
import requests
import os
import logging
from uuid import uuid4

# Configuración de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')

# Inicializar Flask
app = Flask(__name__)

# Obtener ID del nodo desde la variable de entorno
node_id = os.environ.get('NODE_ID')
with open(f'/app/config/node{node_id}.json') as f:
    config = json.load(f)

# Configuración de vecinos y datos
neighbors = config['neighbors']
data = {}
received_messages = set()  # Para evitar procesar mensajes duplicados
logical_clock = 0  # Reloj lógico del nodo

@app.route('/gossip', methods=['POST'])
def receive_gossip():
    """Recibe datos de Gossip de otros nodos."""
    global logical_clock
    new_data = request.json
    received_clock = new_data.get('clock', 0)
    message_id = new_data.get('id')

    # Actualizar el reloj lógico usando el algoritmo de Lamport
    logical_clock = max(logical_clock, received_clock) + 1

    # Evitar procesar mensajes duplicados
    if message_id in received_messages:
        logging.info(f"Nodo {node_id} ignoró mensaje duplicado con ID {message_id}.")
        return jsonify({"status": "duplicate"}), 200

    received_messages.add(message_id)

    # Actualizar los datos
    data.update(new_data.get('data', {}))
    logging.info(f"Nodo {node_id} recibió datos: {new_data['data']} (Clock: {logical_clock}).")
    return jsonify({"status": "ok"})

@app.route('/data', methods=['GET'])
def get_data():
    """Devuelve los datos almacenados en el nodo."""
    return jsonify({"data": data, "clock": logical_clock})

def gossip():
    """Propaga datos a nodos vecinos periódicamente."""
    global logical_clock
    while True:
        if data:
            target = random.choice(neighbors)
            logical_clock += 1  # Incrementar el reloj lógico antes de enviar
            message_id = str(uuid4())  # Generar un ID único para este mensaje
            gossip_data = {"data": data, "clock": logical_clock, "id": message_id}
            try:
                requests.post(f"http://{target}:5000/gossip", json=gossip_data, timeout=1)
                logging.info(f"Nodo {node_id} envió datos a {target} (Clock: {logical_clock}).")
            except requests.exceptions.RequestException:
                logging.error(f"Nodo {node_id} no pudo enviar gossip a {target}.")
        time.sleep(5)

if __name__ == '__main__':
    # Iniciar el hilo de Gossip
    from threading import Thread
    gossip_thread = Thread(target=gossip)
    gossip_thread.start()

    # Iniciar Flask
    app.run(host='0.0.0.0', port=5000)
