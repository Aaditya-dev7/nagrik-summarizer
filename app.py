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

    # Too short
    if len(text) < 10:
        return True

    # Only single word with no spaces (likely gibberish)
    if ' ' not in text and len(text) > 15:
        return True

    # Random keyboard mashing (mostly consonants, no vowels pattern)
    vowels = set('aeiouAEIOU')
    consonant_count = sum(1 for c in text if c.isalpha() and c not in vowels)
    vowel_count = sum(1 for c in text if c in vowels)
    if consonant_count > 10 and vowel_count == 0:
        return True

    # Repeated characters (e.g., "asdfasdfasdf" or "aaaaaaa")
    if len(set(text.lower())) < 4 and len(text) > 10:
        return True

    return False

# =============================
# INDIA LOCATIONS (expanded)
# =============================

INDIA_CITIES = [
"mumbai","delhi","pune","bangalore","hyderabad",
"chennai","kolkata","ahmedabad","surat","jaipur",
"lucknow","kanpur","nagpur","indore","bhopal",
"patna","ludhiana","agra","nashik","faridabad",
"baner","kothrud","hadapsar","andheri","vashi",
"nerul","thane","navi mumbai","powai","dadar",
"bandra","juhu","churchgate","colaba","worli",
"malad","borivali","kandivali","goregaon","bhandup",
"thane","kalyan","dombivli","virar","vasai",
"gurgaon","noida","ghaziabad","rohini","janakpuri",
"rajouri","karol","lajpat","connaught","chandni"
]

def detect_location(text):

    t = text.lower()

    for city in INDIA_CITIES:
        if city in t:
            return city.title()

    # Check for common location indicators
    if any(word in t for word in ["near", "at ", "in ", "around", "beside", "opposite", "behind", "front of"]):
        return "Location mentioned"

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

def calculate_score(text, location, category="General Issue"):

    score = 40  # Base score for valid text

    # Length bonus (more detailed reports)
    word_count = len(text.split())
    if word_count >= 3:
        score += 5
    if word_count >= 5:
        score += 5
    if word_count >= 8:
        score += 5
    if word_count >= 12:
        score += 5
    if word_count >= 15:
        score += 5
    if word_count >= 20:
        score += 5

    # Location bonus
    if location != "Unknown":
        score += 15
    if location == "Location mentioned":
        score += 5

    # Category detection bonus
    if category != "General Issue":
        score += 10

    # Sentence structure bonus (periods, commas indicate proper sentences)
    if '.' in text:
        score += 5
    if ',' in text:
        score += 3

    # Urgency words bonus
    urgency_words = ["urgent", "emergency", "dangerous", "hazard", "accident", "immediately", "asap", "serious"]
    if any(word in text.lower() for word in urgency_words):
        score += 5

    return min(score, 100)  # Cap at 100

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
            "ok": False,
            "error":"Abusive language detected. Please use respectful language."
        }),400

    if is_garbage(text):

        return jsonify({
            "ok": False,
            "error":"Invalid complaint text. Please provide more details."
        }),400

    location = detect_location(text)

    category = detect_category(text)

    score = calculate_score(text, location, category)

    status = "accepted" if score >= 50 else "flagged"

    summary = f"{category}, {location}, No Injury, Low"

    return jsonify({
        "ok": True,
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
