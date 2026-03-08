from flask import Flask, request, jsonify, render_template_string
import pickle
import re

app = Flask(__name__)

# ==========================================
# 1. LOAD MODEL
# ==========================================
print("🔧 Loading Model...")

model = None
vectorizer = None

try:
    with open('simple_model.pkl', 'rb') as f:
        model = pickle.load(f)
    with open('simple_vectorizer.pkl', 'rb') as f:
        vectorizer = pickle.load(f)
    print("✅ Model Loaded!")
except Exception as e:
    print(f"❌ Error: {e}")

# ==========================================
# 2. HELPER: EXTRACT LOCATION (IF EXISTS)
# ==========================================
def extract_location_if_present(text):
    """
    Agar user text me location likha ho (jaise 'Kothrud', 'Baner'),
    toh use nikal lo. Nahi toh 'Unknown' return karo.
    """
    # List of common locations in Pune
    known_locations = [
        "Kothrud", "Baner", "Hadapsar", "Shivajinagar", "Pune Station", 
        "Camp", "Viman Nagar", "Aundh", "Pimple Saudagar", "Karjat",
        "Kharadi", "Magarpatta", "Bibvewadi"
    ]
    
    text_lower = text.lower()
    found_loc = "Unknown"
    
    for loc in known_locations:
        if loc.lower() in text_lower:
            found_loc = loc
            break
            
    return found_loc

# ==========================================
# 3. HTML
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NagrikGPT Summarizer</title>
    <style>
        body { font-family: sans-serif; background-color: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background: white; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); width: 600px; }
        h2 { text-align: center; color: #333; }
        textarea { width: 100%; height: 120px; padding: 12px; margin-bottom: 20px; border: 1px solid #ccc; border-radius: 8px; }
        button { width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #0056b3; }
        #result { margin-top: 25px; padding: 15px; background: #e9ecef; border-radius: 8px; display: none; border-left: 5px solid #007bff; }
        .loader { display: none; text-align: center; margin-top: 15px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h2>NagrikGPT Smart Summarizer</h2>
        <textarea id="inputText" placeholder="Enter complaint here..."></textarea>
        <button onclick="summarize()">Summarize</button>
        <div class="loader" id="loader">Processing...</div>
        <div id="result"><span id="summaryText"></span></div>
    </div>

    <script>
        async function summarize() {
            const text = document.getElementById('inputText').value;
            const loader = document.getElementById('loader');
            const resultDiv = document.getElementById('result');
            
            if (!text) return alert("Enter text!");

            loader.style.display = 'block';
            resultDiv.style.display = 'none';

            const response = await fetch('/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });

            const data = await response.json();
            loader.style.display = 'none';
            resultDiv.style.display = 'block';
            document.getElementById('summaryText').innerText = data.summary;
        }
    </script>
</body>
</html>
"""

# ==========================================
# 4. ROUTE
# ==========================================

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/summarize', methods=['POST'])
def summarize():
    if model is None: return jsonify({"summary": "Model not loaded"})

    data = request.json
    text = data.get('text', '')

    # 1. Detect Real Location
    detected_loc = extract_location_if_present(text)

    # 2. Predict Summary (Model pura string dega)
    # Example Output: "Street Light, Shivajinagar, No Injury, Low"
    text_vector = vectorizer.transform([text])
    raw_prediction = model.predict(text_vector)[0]

    # 3. Clean the Prediction (Replace Guessed Location with Real Location)
    # Split by comma
    parts = raw_prediction.split(',')
    
    # Structure: Category, Location, Injury, Urgency
    # We want to replace the 2nd part (Index 1) with our detected location
    
    if len(parts) >= 2:
        parts[1] = detected_loc # Replace location
        final_summary = ", ".join(parts)
    else:
        final_summary = raw_prediction # Fallback

    return jsonify({"summary": final_summary})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
