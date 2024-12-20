from gevent import monkey
monkey.patch_all()

import json
import threading
import datetime
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO

# Global variables
app = Flask(__name__)
socketio = SocketIO(app, async_mode='gevent')  # Using Gevent as async mode

# MQTT Broker details
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "sensor/mq2"


# Connect to MongoDB
def get_mongo_collection():
    # MongoDB connection details
    MONGO_URI = "mongodb+srv://user1:asdfsdfdzc13reqfvdf@cluster0.cve6w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    DB_NAME = "iot_data"
    COLLECTION_NAME = "mqtt_messages"
    """Initialize MongoDB client and return the collection."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    return db[COLLECTION_NAME]


def save_to_database(data):
    """Try to save data to MongoDB."""
    try:
        get_mongo_collection().insert_one(data)
        print(f"Data inserted into MongoDB: {data}")

    except Exception as e:
        print(f"Failed to save data to MongoDB: {e}")


def on_connect(client, userdata, flags, rc):
    """Callback when the client connects to the MQTT broker."""
    if rc == 0:
        print("Connected to MQTT Broker")
        client.subscribe(TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")


def on_message(client, userdata, msg):
    """Callback when a message is received from the MQTT broker."""
    try:
        payload = json.loads(msg.payload.decode())
        timestamp = payload["timestamp"]
        value = float(payload["value"])

        print(f"Data received -> Timestamp: {timestamp}, Value: {value}")

        data = {
            "timestamp": datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S"),
            "value": value,
            "topic": msg.topic,
        }

        # Save to MongoDB
        save_to_database(data)

        # Emit data to WebSocket clients
        socketio.emit('new_data', data)

    except Exception as e:
        print(f"Error processing message: {e}")


def mqtt_thread():
    """Run the MQTT client."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_forever()


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


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket client connection."""
    client_ip = request.remote_addr
    client_port = request.environ.get('REMOTE_PORT')
    print(f'Client connected from {client_ip}:{client_port}')


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket client disconnection."""
    client_ip = request.remote_addr
    client_port = request.environ.get('REMOTE_PORT')
    print(f'Client disconnected from {client_ip}:{client_port}')


def main():
    """Main entry point of the application."""
    print('Starting MQTT client in a separate thread...')
    mqtt_thread_instance = threading.Thread(target=mqtt_thread, daemon=True)
    mqtt_thread_instance.start()

    print('Starting Flask-SocketIO server...')
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)


if __name__ == '__main__':
    main()
