import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# ✅ Nový oficiálny Gemini SDK (nie google-generativeai)
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

# =========================
# GEMINI KONFIGURÁCIA
# =========================

# Nastav v Render Environment:
# GEMINI_API_KEY=xxxxxxxxxxxxxxxx
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"

# Model môžeš zmeniť cez ENV premennú GEMINI_MODEL
# Odporúčané (marec 2026):
# - gemini-2.5-flash  (stabilný)
# - gemini-flash-latest (alias na najnovší Flash)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not API_KEY:
    raise RuntimeError("Chýba GEMINI_API_KEY v environment variables.")

client = genai.Client(api_key=API_KEY)

# =========================
# SYSTEM INSTRUCTION
# =========================

SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre Strednú odbornú školu informačných technológií,
Ostrovského 1, Košice.

Poskytuj presné a profesionálne informácie.

IDENTITA:
- SOŠ IT Ostrovského 1, Košice
- Adresa: Ostrovského 1, 040 01 Košice
- Email: skola@ostrovskeho.sk
- Tel: +421 55 643 68 91
- Riaditeľka: Ing. Elena Tibenská

ŠTUDIJNÉ ODBORY 2026/2027:
1. Inteligentné technológie
2. Informačné a sieťové technológie
3. Programovanie digitálnych technológií
4. Správca inteligentných a digitálnych systémov
5. Grafik digitálnych médií

GDPR:
Neposkytuj osobné údaje žiakov.
Ak ide o interné údaje (rozvrh, suplovanie),
odkáž na EduPage alebo sekretariát.

Odpovedaj profesionálne a priateľsky.
Uveď, že informácie sú platné pre školský rok 2025/2026 alebo 2026/2027.
""".strip()


# =========================
# ROUTES
# =========================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "Prázdna správa"}), 400

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.4,
                max_output_tokens=800,
            ),
        )

        return jsonify({
            "response": response.text,
            "status": "success"
        })

    except Exception as e:
        return jsonify({
            "error": f"{type(e).__name__}: {str(e)}",
            "status": "error"
        }), 500


# =========================
# START SERVER
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
