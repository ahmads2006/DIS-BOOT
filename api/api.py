from flask import Flask, request, jsonify
import threading
import os

app = Flask(__name__)

API_KEY = os.getenv("BOT_API_KEY", "secret123")

@app.route("/api/start-exam", methods=["POST"])
def start_exam():
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    user_id = data.get("discord_user_id")
    role = data.get("role")

    # 👇 هنا تنادي منطق البوت نفسه
    print(f"Start exam for {user_id} role={role}")

    return jsonify({"status": "exam_started"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
def run_api():
    app.run(host="0.0.0.0", port=5000, debug=False)
