import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# ✅ google-genai (nový SDK)
try:
    from google import genai
    from google.genai import types
except Exception:
    import google.genai as genai  # fallback pre niektoré verzie
    from google.genai import types

app = Flask(__name__)
CORS(app)

# =========================
# GEMINI KONFIGURÁCIA
# =========================
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not API_KEY:
    raise RuntimeError("Chýba GEMINI_API_KEY v environment variables (Render).")

client = genai.Client(api_key=API_KEY)

# =========================
# SYSTEM INSTRUCTION
# =========================
SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre Strednú odbornú školu informačných technológií, Ostrovského 1, Košice.
Odpovedaj profesionálne, priateľsky a v slovenčine.

IDENTITA:
- SOŠ IT Ostrovského 1, Košice
- Adresa: Ostrovského 1, 040 01 Košice
- Email: skola@ostrovskeho.sk
- Tel: +421 55 643 68 91
- Riaditeľka: Ing. Elena Tibenská

ŠTUDIJNÉ ODBORY (2026/2027):
1. Inteligentné technológie
2. Informačné a sieťové technológie
3. Programovanie digitálnych technológií
4. Správca inteligentných a digitálnych systémov
5. Grafik digitálnych médií

GDPR:
- Neposkytuj osobné údaje žiakov.
- Ak ide o interné veci (rozvrh, suplovanie), odkáž na EduPage alebo sekretariát.

V odpovediach môžeš dodať, že informácie sú platné pre školský rok 2025/2026 alebo 2026/2027.
""".strip()


# =========================
# ROUTES
# =========================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """
    Dôležité: Frontend očakáva JSON vždy vo formáte:
      { "response": "..." }
    Preto aj pri chybe vždy vraciame 'response', aby nevypísalo
    "Server vrátil neplatné dáta."
    """
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
        # Log do Render (aby si videl dôvod v Logs)
        print("CHAT ERROR:", repr(e))

        # Frontend-safe odpoveď (stále platný JSON)
        return jsonify({"response": "Nastala chyba servera. Skús to prosím o chvíľu."})


# =========================
# START SERVER
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
