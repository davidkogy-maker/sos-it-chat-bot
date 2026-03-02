import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# ✅ google-genai (nový SDK)
try:
    from google import genai
    from google.genai import types
except Exception:
    import google.genai as genai
    from google.genai import types

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Keď dáš na Render DEBUG=1, do odpovede sa vypíše detail chyby
DEBUG = os.getenv("DEBUG", "0") == "1"

if not API_KEY:
    raise RuntimeError("Chýba GEMINI_API_KEY v Render environment variables.")

client = genai.Client(api_key=API_KEY)

SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre SOŠ IT Ostrovského 1, Košice.
Odpovedaj profesionálne, priateľsky a v slovenčine.

Študijné odbory (2026/2027):
1. Inteligentné technológie
2. Informačné a sieťové technológie
3. Programovanie digitálnych technológií
4. Správca inteligentných a digitálnych systémov
5. Grafik digitálnych médií

GDPR: Neposkytuj osobné údaje žiakov.
""".strip()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()

        if not user_message:
            return jsonify({"response": "Napíš prosím otázku 🙂"})

        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.4,
                max_output_tokens=800,
            ),
        )

        text = (resp.text or "").strip()
        if not text:
            text = "Ospravedlňujem sa, odpoveď sa nepodarila vygenerovať."

        return jsonify({"response": text})

    except Exception as e:
        # Render Logs
        print("CHAT ERROR:", repr(e))

        # Frontend vždy dostane valid JSON
        if DEBUG:
            return jsonify({"response": f"DEBUG ERROR: {type(e).__name__}: {e}"})
        return jsonify({"response": "Nastala chyba servera. Skús to prosím o chvíľu."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
