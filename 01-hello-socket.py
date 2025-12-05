from flask import Flask, render_template
from flask_socketio import SocketIO, emit, send

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"

# Enable CORS for Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*")


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    print("Client connected")
    send("Welcome to the server!")


@socketio.on("message")
def handle_message(msg):
    print(f"Received: {msg}")
    send(msg, broadcast=True)  # Broadcast to all clients


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


if __name__ == "__main__":
    socketio.run(app, debug=True)
