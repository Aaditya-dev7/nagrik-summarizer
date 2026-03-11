from flask import Flask, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

# =============================
# BAD WORDS
# =============================

BAD_WORDS = [
    "idiot","stupid","bloody","abuse",
    "harami","nalayak","chutiya","madarchod"
]

def contains_bad_words(text):

    t = text.lower()

    for w in BAD_WORDS:
        if w in t:
            return True

    return False

# =============================
# GARBAGE TEXT
# =============================

def is_garbage(text):

    if len(text) < 5:
        return True

    if re.fullmatch(r"[a-zA-Z]{8,}", text):
        return True

    return False

# =============================
# INDIA LOCATIONS (sample)
# =============================

INDIA_CITIES = [
"mumbai","delhi","pune","bangalore","hyderabad",
"chennai","kolkata","ahmedabad","surat",
"baner","kothrud","hadapsar","andheri","vashi"
]

def detect_location(text):

    t = text.lower()

    for city in INDIA_CITIES:
        if city in t:
            return city.title()

    return "Unknown"

# =============================
# CATEGORY DETECTION
# =============================

def detect_category(text):

    t = text.lower()

    if "pothole" in t or "गड्ढा" in t or "खड्डा" in t:
        return "Pothole"

    if "road" in t or "road damage" in t:
        return "Road Damage"

    if "garbage" in t or "trash" in t or "कचरा" in t:
        return "Garbage Collection"

    if "dump" in t:
        return "Illegal Dumping"

    if "light" in t:
        return "Street Light"

    if "water leak" in t or "pipeline" in t:
        return "Water Leakage"

    if "drain" in t:
        return "Drainage Block"

    if "tree" in t:
        return "Tree Falling Risk"

    if "sewage" in t:
        return "Sewage Overflow"

    if "park" in t:
        return "Park Maintenance"

    return "General Issue"

# =============================
# REPORT SCORE
# =============================

def calculate_score(text,location):

    score = 0

    if not is_garbage(text):
        score += 50

    if location != "Unknown":
        score += 50

    return score

# =============================
# HEALTH
# =============================

@app.route("/health")
def health():

    return jsonify({"status":"running"})


# =============================
# SUMMARIZE
# =============================

@app.route("/summarize", methods=["POST"])
def summarize():

    data = request.json
    text = data.get("text","").strip()

    if contains_bad_words(text):

        return jsonify({
            "error":"Abusive language detected. Please use respectful language."
        }),400

    if is_garbage(text):

        return jsonify({
            "error":"Invalid complaint text."
        }),400

    location = detect_location(text)

    category = detect_category(text)

    score = calculate_score(text,location)

    status = "accepted" if score >= 70 else "flagged"

    summary = f"{category}, {location}, No Injury, Low"

    return jsonify({

        "summary":summary,
        "category":category,
        "location":location,
        "report_score":score,
        "status":status
    })


# =============================
# START
# =============================

import os

if __name__ == "__main__":

    port = int(os.environ.get("PORT",10000))

    app.run(host="0.0.0.0",port=port)
