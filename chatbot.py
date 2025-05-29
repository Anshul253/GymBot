from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import bcrypt
import jwt
import datetime
import json
from spellchecker import SpellChecker
from difflib import get_close_matches
import re
from bson import ObjectId

app = Flask(__name__)
CORS(app)
SECRET_KEY = "your_super_secret_key"

client = MongoClient("mongodb+srv://anshulsinghrajput2208:w8o3U8wOQ4j4nXqP@cluster0.ibsnjub.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["gymbot"]
users_collection = db["users"]
chats_collection = db["chats"]
messages_collection = db["messages"]

with open("gym_chatbot_data.json", "r") as f:
    data = json.load(f)

body_parts = data["exercises_by_body_part"]
exercises = data["exercises_by_name"]
spell = SpellChecker()

session_state = {
    "last_body_part": None,
    "last_index": 0,
    "default_batch_size": 5
}

def correct_text(text):
    return " ".join([spell.correction(word) or word for word in text.split()])

def find_by_body_part(query, start_index=0, amount=5):
    corrected = correct_text(query.lower().strip())
    for key in body_parts:
        if corrected == key.lower():
            session_state["last_body_part"] = key
            session_state["last_index"] = start_index + amount
            entries = body_parts[key]
            sliced = entries[start_index:start_index + amount]
            if not sliced:
                return f"No more exercises for {key}."
            return f"Exercises for {key} (Showing {start_index+1} to {start_index+len(sliced)}):\n\n" + "\n\n".join([
                f"**{e['name'].title()}**\nDescription: {e['description']}\nEquipment: {e['equipment']}\nLevel: {e['level']}"
                for e in sliced])
    return f"No exercises found for body part '{query}'."

def find_by_name(query):
    key = correct_text(query.lower().strip())
    if key in exercises:
        ex = exercises[key]
        return f"**{key.title()}**\nBody Part: {ex['body_part']}\nDescription: {ex['description']}\nEquipment: {ex['equipment']}\nLevel: {ex['level']}"
    match = get_close_matches(key, exercises.keys(), n=1, cutoff=0.7)
    if match:
        ex = exercises[match[0]]
        return f"**{match[0].title()}**\nBody Part: {ex['body_part']}\nDescription: {ex['description']}\nEquipment: {ex['equipment']}\nLevel: {ex['level']}"
    return f"No information found for exercise '{query}'."

def parse_more_command(query):
    match = re.match(r"(\d+)?\s*more", query.lower())
    if match:
        return int(match.group(1)) if match.group(1) else session_state["default_batch_size"]
    return None

def chat_logic(query):
    query = query.strip().lower()
    count = parse_more_command(query)
    if count is not None:
        if session_state["last_body_part"]:
            return find_by_body_part(session_state["last_body_part"], session_state["last_index"], count)
        else:
            return "Please ask about a body part first."
    if query in exercises:
        return find_by_name(query)
    elif query in [bp.lower() for bp in body_parts]:
        return find_by_body_part(query)
    else:
        part_result = find_by_body_part(query)
        if "No exercises found" not in part_result:
            return part_result
        return find_by_name(query)

# ---------------- AUTH -------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    if users_collection.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 409
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    users_collection.insert_one({"email": email, "password": hashed_pw})
    return jsonify({"message": "Registered successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    user = users_collection.find_one({"email": email})
    if not user or not bcrypt.checkpw(password.encode(), user["password"]):
        return jsonify({"error": "Invalid credentials"}), 401
    token = jwt.encode({"email": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET_KEY, algorithm="HS256")
    return jsonify({"message": "Login successful", "token": token})

# ---------------- CHAT -------------------

@app.route("/chat/new", methods=["POST"])
def create_chat():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return jsonify({"error": "Invalid token"}), 403

    title = request.json.get("title", "New Chat")
    chat_id = chats_collection.insert_one({
        "user_email": payload["email"],
        "title": title,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow()
    }).inserted_id
    return jsonify({"chat_id": str(chat_id)})

@app.route("/chats", methods=["GET"])
def get_chats():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return jsonify({"error": "Invalid token"}), 403

    chats = list(chats_collection.find({"user_email": payload["email"]}))
    return jsonify([{"chat_id": str(c["_id"]), "title": c["title"]} for c in chats])

@app.route("/chat/<chat_id>/messages", methods=["GET"])
def get_messages(chat_id):
    messages = list(messages_collection.find({"chat_id": ObjectId(chat_id)}).sort("timestamp", 1))
    return jsonify([
        {"sender": m["sender"], "content": m["content"], "timestamp": m["timestamp"].isoformat()} for m in messages
    ])

@app.route("/chat/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return jsonify({"error": "Invalid token"}), 403

    chats_collection.delete_one({"_id": ObjectId(chat_id), "user_email": payload["email"]})
    messages_collection.delete_many({"chat_id": ObjectId(chat_id)})
    return jsonify({"message": "Chat deleted"})

@app.route("/chat", methods=["POST"])
def chat():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return jsonify({"error": "Invalid token"}), 403

    query = request.json.get("message", "")
    chat_id = request.json.get("chat_id")
    if not query or not chat_id:
        return jsonify({"error": "Missing data"}), 400

    reply = chat_logic(query)
    messages_collection.insert_many([
        {"chat_id": ObjectId(chat_id), "sender": "user", "content": query, "timestamp": datetime.datetime.utcnow()},
        {"chat_id": ObjectId(chat_id), "sender": "bot", "content": reply, "timestamp": datetime.datetime.utcnow()}
    ])
    chats_collection.update_one({"_id": ObjectId(chat_id)}, {"$set": {"updated_at": datetime.datetime.utcnow()}})
    return jsonify({"reply": reply})

# ---------------- PROFILE -------------------

@app.route("/change-password", methods=["POST"])
def change_password():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user = users_collection.find_one({"email": payload["email"]})
    except:
        return jsonify({"error": "Invalid token"}), 403

    data = request.json
    old_pw = data.get("old_password")
    new_pw = data.get("new_password")

    if not bcrypt.checkpw(old_pw.encode(), user["password"]):
        return jsonify({"error": "Incorrect current password"}), 401

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt())
    users_collection.update_one({"email": payload["email"]}, {"$set": {"password": new_hash}})
    return jsonify({"message": "Password updated successfully"})

# ---------------- MAIN -------------------

if __name__ == "__main__":
    app.run(debug=True)
