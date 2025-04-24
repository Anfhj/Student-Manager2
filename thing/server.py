
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

students = {}       # security_key -> session info
student_sockets = {}  # sid -> security_key
admin_rooms = {}    # admin_id -> set of security_keys

@app.route("/register", methods=["POST"])
def register_student():
    security_key = str(uuid.uuid4())[:6]  # Short code
    students[security_key] = {
        "allowed_sites": [],
        "lockdown": False,
        "messages": []
    }
    return jsonify({"security_key": security_key})

@app.route("/admin/connect", methods=["POST"])
def admin_connect():
    data = request.json
    admin_id = data["admin_id"]
    key = data["security_key"]

    if key not in students:
        return jsonify({"error": "Invalid security key"}), 404

    admin_rooms.setdefault(admin_id, set()).add(key)
    return jsonify({"status": "connected", "student_info": students[key]})

@app.route("/admin/send", methods=["POST"])
def admin_send():
    data = request.json
    admin_id = data["admin_id"]
    key = data["security_key"]
    action = data["action"]

    if key not in students:
        return jsonify({"error": "Student not found"}), 404

    if action == "message":
        msg = data["message"]
        students[key]["messages"].append({"from": "admin", "text": msg})
        socketio.emit("message", {"from": "admin", "text": msg}, room=key)
    elif action == "lockdown":
        lockdown = data["lockdown"]
        sites = data.get("allowed_sites", [])
        students[key]["lockdown"] = lockdown
        students[key]["allowed_sites"] = sites
        socketio.emit("update_lockdown", {"lockdown": lockdown, "allowed_sites": sites}, room=key)

    return jsonify({"status": "sent"})

@socketio.on("connect_student")
def connect_student(data):
    key = data.get("security_key")
    if key in students:
        join_room(key)
        student_sockets[request.sid] = key
        emit("connected", {"status": "connected"})
    else:
        emit("error", {"message": "Invalid key"})

@socketio.on("student_message")
def student_message(data):
    key = student_sockets.get(request.sid)
    msg = data["message"]
    if key:
        students[key]["messages"].append({"from": "student", "text": msg})
        socketio.emit("message", {"from": "student", "text": msg}, room=key)

@socketio.on("disconnect")
def disconnect():
    sid = request.sid
    key = student_sockets.pop(sid, None)
    if key:
        leave_room(key)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050)