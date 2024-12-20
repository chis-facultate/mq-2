import eventlet
eventlet.monkey_patch()

import threading
import json
import paho.mqtt.client as mqtt
from pymongo import MongoClient
import datetime
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO

# Global variables
app = Flask(__name__)  # Flask app instance
socketio = SocketIO(app, cors_allowed_origins="*")
# MongoDB connection details
MONGO_URI = "mongodb+srv://user1:asdfsdfdzc13reqfvdf@cluster0.cve6w.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB URI
DB_NAME = "iot_data"
COLLECTION_NAME = "mqtt_messages"
# MQTT Broker details
BROKER = "broker.hivemq.com"  # Replace with your broker address
PORT = 1883
TOPIC = "sensor/mq2"  # Replace with your topic
# Buffer for storing data when MongoDB is unavailable
buffer = []

# Connect to MongoDB
try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = mongo_client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print("MongoDB connected successfully.")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    mongo_client = None


def save_to_database(data):
    """Try to save data to MongoDB. If it fails, buffer it."""
    global buffer
    try:
        # Check MongoDB connection
        if mongo_client is None or not mongo_client.is_primary:
            raise Exception("MongoDB not connected")

        # Insert data into MongoDB
        collection.insert_one(data)
        print(f"Data inserted into MongoDB: {data}")

        # Retry inserting buffered data
        retry_buffered_data()

    except Exception as e:
        print(f"Failed to save data to MongoDB: {e}")
        buffer.append(data)
        print(f"Data buffered: {data}")


def retry_buffered_data():
    """Retry inserting buffered data into MongoDB."""
    global buffer
    successful_inserts = []
    for data in buffer:
        try:
            collection.insert_one(data)
            print(f"Buffered data inserted: {data}")
            successful_inserts.append(data)
        except Exception as e:
            print(f"Failed to retry buffered data: {e}")
            break  # Stop if insertion fails again

    # Remove successfully inserted data from buffer
    buffer = [item for item in buffer if item not in successful_inserts]


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
        # Decode payload and parse as JSON
        payload = json.loads(msg.payload.decode())

        # Extract fields
        timestamp = payload["timestamp"]
        value = float(payload["value"])  # Ensure 'value' is treated as a float

        # Log or store data
        print(f"Data received -> Timestamp: {timestamp}, Value: {value}")

        # Prepare data to insert into MongoDB
        data = {
            "timestamp": datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S"),
            "value": float(value),
            "topic": msg.topic,
        }

        # Attempt to save the data to the database
        save_to_database(data)

    except Exception as e:
        print(f"Error processing message: {e}")


def mqtt_thread():
    """Run the MQTT client."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_forever()


# Endpoints
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


# SocketIO event for client connection
@socketio.on('connect')
def handle_connect():
    client_ip = request.remote_addr
    client_port = request.environ.get('REMOTE_PORT')
    print(f'Client connected from {client_ip}:{client_port}')


# SocketIO event for client disconnection
@socketio.on('disconnect')
def handle_disconnect():
    client_ip = request.remote_addr
    client_port = request.environ.get('REMOTE_PORT')
    print(f'Client disconnected from {client_ip}:{client_port}')


def main():
    # Start MQTT client in a separate thread
    threading.Thread(target=mqtt_thread, daemon=True).start()

    print('MQTT client started')

    # Run Flask-SocketIO server
    socketio.run(app, host='127.0.0.1', port='5000', debug=True, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
