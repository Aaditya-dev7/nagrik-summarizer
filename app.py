from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import re
import spacy
import os
import requests

app = Flask(__name__)
CORS(app)

# ================================
# LOAD NLP MODEL
# ================================

nlp = spacy.load("en_core_web_sm")

# ================================
# LOAD ML MODEL
# ================================

model = None
vectorizer = None

try:
    with open("simple_model.pkl", "rb") as f:
        model = pickle.load(f)

    with open("simple_vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)

    print("✅ ML model loaded")

except Exception as e:
    print("❌ ML model error:", e)

# ================================
# BAD WORD DETECTION
# ================================

BAD_WORDS = [
    "idiot","stupid","bloody","abuse","harami","nalayak",
    "gali","madarchod","bhosdike","chutiya"
]

def contains_bad_words(text):

    t = text.lower()

    for word in BAD_WORDS:
        if word in t:
            return True

    return False

# ================================
# GARBAGE TEXT DETECTION
# ================================

def is_garbage(text):

    text = text.strip()

    if len(text) < 5:
        return True

    if re.fullmatch(r"[a-zA-Z]{8,}", text):
        return True

    return False

# ================================
# LOCATION DETECTION
# ================================

def detect_location(text):

    doc = nlp(text)

    for ent in doc.ents:
        if ent.label_ in ["GPE","LOC"]:
            return ent.text

    return "Unknown"

# ================================
# CATEGORY DETECTION
# ================================

def detect_category(text):

    t = text.lower()

    categories = {

        "Pothole":[
            "pothole","खड्डा","गड्ढा"
        ],

        "Road Damage":[
            "road damage","road crack","रस्ता खराब","सड़क टूटी"
        ],

        "Garbage Collection":[
            "garbage","trash","waste","कचरा"
        ],

        "Illegal Dumping":[
            "dump","illegal dump","कचरा फेकना"
        ],

        "Street Light":[
            "street light","light not working","लाईट बंद"
        ],

        "Water Leakage":[
            "water leak","pipeline leak","पाणी गळती"
        ],

        "Drainage Block":[
            "drain","drainage","नाली बंद"
        ],

        "Tree Falling Risk":[
            "tree falling","झाड पडणे"
        ],

        "Sewage Overflow":[
            "sewage","sewer","सांडपाणी"
        ],

        "Park Maintenance":[
            "park","garden","उद्यान"
        ]
    }

    for category,keywords in categories.items():

        for word in keywords:

            if word in t:
                return category

    return None

# ================================
# IMAGE VALIDATION (PLACEHOLDER)
# ================================

def verify_image():

    # future: integrate YOLO or CV model
    return "unknown"


def verify_image_with_hf(image_url: str, text: str):

    url = str(image_url or '').strip()
    if not url:
        return { "status": "missing" }

    token = os.environ.get('HF_API_TOKEN', '').strip()
    if not token:
        return { "status": "unknown" }

    # Using a public zero-shot image classification model with candidate labels
    # so we can score whether the photo matches a civic issue description.
    endpoint = os.environ.get('HF_IMAGE_VERIFY_URL', 'https://api-inference.huggingface.co/models/openai/clip-vit-base-patch32')
    headers = { 'Authorization': f'Bearer {token}' }

    labels = [
        "photo relevant to the complaint",
        "unrelated photo",
        "random image",
        "street pothole",
        "garbage on street",
        "broken street light",
        "water leakage",
        "drainage blockage",
        "sewage overflow",
        "road damage",
    ]

    try:
        payload = { 'inputs': image_url, 'parameters': { 'candidate_labels': labels } }
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        if resp.status_code >= 400:
            return { "status": "unknown" }
        data = resp.json() if resp.content else None

        # HF returns either {labels:[], scores:[]} or a list; normalize
        if isinstance(data, dict) and isinstance(data.get('scores'), list):
            scores = data.get('scores')
            lab = data.get('labels')
            top_score = float(scores[0]) if scores else 0.0
            top_label = str(lab[0]) if isinstance(lab, list) and lab else ''
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            top = data[0]
            top_score = float(top.get('score') or 0.0)
            top_label = str(top.get('label') or '')
        else:
            return { "status": "unknown" }

        # conservative threshold
        if top_score >= 0.55 and top_label != 'unrelated photo' and top_label != 'random image':
            return { "status": "valid", "score": top_score, "label": top_label }
        return { "status": "invalid", "score": top_score, "label": top_label }
    except Exception:
        return { "status": "unknown" }

# ================================
# FAKE REPORT SCORE
# ================================

def calculate_score(text,location,image_status):

    score = 0

    if not is_garbage(text):
        score += 40

    if location != "Unknown":
        score += 30

    if image_status == "valid":
        score += 30

    return score

# ================================
# HEALTH CHECK
# ================================

@app.route("/health")
def health():

    return jsonify({
        "status":"running"
    })

# ================================
# SUMMARIZE API
# ================================

@app.route("/summarize", methods=["POST"])
def summarize():

    data = request.json
    text = data.get("text","").strip()
    image_url = data.get("image_url", "") if isinstance(data, dict) else ""

    # BAD WORD BLOCK
    if contains_bad_words(text):

        return jsonify({
            "error":"Abusive language detected. Please use respectful language."
        }),400

    # GARBAGE BLOCK
    if is_garbage(text):

        return jsonify({
            "error":"Invalid complaint text."
        }),400

    # LOCATION
    location = detect_location(text)

    # CATEGORY
    category = detect_category(text)

    # ML FALLBACK
    if category is None and model is not None:

        try:
            text_vector = vectorizer.transform([text])
            raw_prediction = model.predict(text_vector)[0]

            category = raw_prediction.split(",")[0]

        except:
            category = "General Issue"

    # IMAGE CHECK
    img = verify_image_with_hf(image_url, text)
    image_status = img.get('status', 'unknown') if isinstance(img, dict) else 'unknown'

    # REPORT SCORE
    score = calculate_score(text,location,image_status)

    if score >= 90:
        status = "accepted"
    else:
        status = "flagged"

    summary = f"{category}, {location}, No Injury, Low"

    return jsonify({

        "summary":summary,
        "category":category,
        "location":location,
        "image_check":image_status,
        "image": img,
        "report_score":score,
        "status":status
    })

# ================================
# START SERVER
# ================================

if __name__ == "__main__":

    print("🚀 NagrikGPT AI service running")

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0",port=port)
