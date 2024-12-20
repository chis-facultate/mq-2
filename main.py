from gevent import monkey

monkey.patch_all()

import logging
import threading
import json
import datetime
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from flask import Flask, request, render_template, jsonify
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from geventwebsocket.exceptions import WebSocketError
from geventwebsocket import WebSocketServer

# Global variables
app = Flask(__name__)
websockets = []
# socketio = SocketIO(app, async_mode='gevent', logger=True, engineio_logger=True)  # Using Gevent as async mode

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Capture all log levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# MQTT Broker details
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "sensor/mq2"


# Connect to MongoDB
def get_mongo_collection():
    """Initialize MongoDB client and return the collection."""
    MONGO_URI = "mongodb+srv://user1:asdfsdfdzc13reqfvdf@cluster0.cve6w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    DB_NAME = "iot_data"
    COLLECTION_NAME = "mqtt_messages"
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]


def save_to_database(data):
    """Try to save data to MongoDB."""
    try:
        get_mongo_collection().insert_one(data)
        logger.debug(f"******** Data inserted into MongoDB: {data}")

    except Exception as e:
        logger.debug(f"******** Failed to save data to MongoDB: {e}")


def on_connect(client, userdata, flags, rc):
    """Callback when the client connects to the MQTT broker."""
    if rc == 0:
        logger.debug("******** Connected to MQTT Broker")
        client.subscribe(TOPIC)
    else:
        logger.debug(f"******** Failed to connect, return code {rc}")


# def on_message(client, userdata, msg):
#     """Callback when a message is received from the MQTT broker."""
#     try:
#         payload = json.loads(msg.payload.decode())
#         timestamp = payload["timestamp"]
#         value = float(payload["value"])
#
#         logger.debug(f"******** Data received -> Timestamp: {timestamp}, Value: {value}")
#
#         data = {
#             "timestamp": datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S"),
#             "value": value,
#             "topic": msg.topic,
#         }
#
#         # Save to MongoDB
#         save_to_database(data)
#
#         # Emit data to WebSocket clients
#         socketio.emit('new_data', data)
#
#     except Exception as e:
#         print(f"Error processing message: {e}")

def on_message(client, userdata, msg):
    """Callback when a message is received from the MQTT broker."""
    try:
        payload = json.loads(msg.payload.decode())
        timestamp = payload["timestamp"]
        value = float(payload["value"])

        logger.debug(f"******** Data received -> Timestamp: {timestamp}, Value: {value}")

        data = {
            "timestamp": datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S"),
            "value": value,
            "topic": msg.topic,
        }

        # Save to MongoDB
        save_to_database(data)

        # Forward the message to all active WebSocket clients
        for ws in websockets:
            try:
                ws.send(json.dumps(data))
            except WebSocketError:
                logger.debug("*** Error sending message to WebSocket.")

    except Exception as e:
        logger.debug(f"*** Error processing message: {e}")


def mqtt_thread():
    """Run the MQTT client in a gevent-friendly way."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    logger.debug('******** before loop_start')
    client.loop_start()  # This is the key change - using loop_start() instead of loop_forever() in gevent
    logger.debug('******** after loop_start')


@app.route('/', methods=['GET'])
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/data', methods=['GET'])
def get_data():
    """Fetch all data from the MongoDB collection."""
    try:
        data = list(get_mongo_collection().find({}, {"_id": 0}))  # Exclude MongoDB ObjectId
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @socketio.on('connect')
# def handle_connect():
#     """Handle WebSocket client connection."""
#     client_ip = request.remote_addr
#     client_port = request.environ.get('REMOTE_PORT')
#     print(f'Client connected from {client_ip}:{client_port}')
#     logger.debug(f'******** Client connected from {client_ip}:{client_port}')
#
#
# @socketio.on('disconnect')
# def handle_disconnect():
#     """Handle WebSocket client disconnection."""
#     client_ip = request.remote_addr
#     client_port = request.environ.get('REMOTE_PORT')
#     print(f'Client disconnected from {client_ip}:{client_port}')
#     logger.debug(f'******** Client disconnected from {client_ip}:{client_port}')

@app.route('/ws')
def websocket_endpoint():
    """WebSocket endpoint."""
    # Check if the request is a WebSocket connection
    ws = request.environ.get('wsgi.websocket')
    if not ws:
        return "WebSocket connection required", 400

    # Add the WebSocket to the global list of connections
    websockets.append(ws)
    logger.debug("*** New WebSocket connection established.")

    try:
        while True:
            pass
            # Keep the connection alive; no need to receive anything unless you want to
            # message = ws.receive()  # Optionally, you can process any received messages
            # if message is None:
            #    break  # WebSocket connection closed, break the loop
    except WebSocketError as e:
        logger.debug(f"*** WebSocket error: {str(e)}")
    finally:
        # Remove the WebSocket from the list when it disconnects
        websockets.remove(ws)
        logger.debug("*** WebSocket disconnected.")

    return "WS CLOSED"


def main():
    """Main entry point of the application."""
    logger.debug('******** Starting MQTT client in a separate thread...')
    #mqtt_thread_instance = threading.Thread(target=mqtt_thread, daemon=True)
    #mqtt_thread_instance.start()
    mqtt_thread()

    logger.debug('******** Starting server...')
    #socketio.run(app, host='127.0.0.1', port=5000, debug=True)
    # Start the Flask server with Gevent WebSocket support
    # server = pywsgi.WSGIServer(('0.0.0.0', 5401), app, handler_class=WebSocketHandler)
    server = WebSocketServer(('0.0.0.0', 8006), app)
    logger.debug("**** Server running")
    server.serve_forever()


main()
