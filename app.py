import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# ====== ENV VARS (Render) ======
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # alebo čo ti reálne funguje

if not API_KEY:
    # Nezabijeme celý server, len v /chat vrátime hlášku
    API_KEY = None
else:
    genai.configure(api_key=API_KEY)

# ====== SYSTEM INSTRUCTION ======
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

Dôležité:
- Keď sa používateľ pýta doplňujúco (napr. "ktorý čo?"), vychádzaj z predchádzajúcej konverzácie.
- Odpovedaj vecne, nestrácaj sa v zbytočných otázkach.
""".strip()


def _to_genai_history(history):
    """
    Očakáva list objektov:
      [{"role":"user","text":"..."}, {"role":"model","text":"..."}]
    Prekonvertuje na formát pre google-generativeai chat.
    """
    out = []
    if not isinstance(history, list):
        return out

    # limit na posledných 12 správ kvôli tokenom
    history = history[-12:]

    for item in history:
        role = item.get("role")
        text = (item.get("text") or "").strip()
        if not text:
            continue

        if role == "user":
            out.append({"role": "user", "parts": [text]})
        elif role in ("model", "assistant", "bot"):
            out.append({"role": "model", "parts": [text]})

    return out


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    # Frontend vždy očakáva { "response": "..." }
    try:
        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        history = data.get("history", [])

        if not user_message:
            return jsonify({"response": "Napíš prosím otázku 🙂"})

        if not API_KEY:
            return jsonify({"response": "Server nie je nakonfigurovaný: chýba GEMINI_API_KEY."})

        # model bez google_search_retrieval (to často robí chaos / obmedzenia / halucinácie)
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 900,  # aby nedokončovalo príliš skoro
            },
        )

        chat_session = model.start_chat(history=_to_genai_history(history))

        resp = chat_session.send_message(user_message)

        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            text = "Ospravedlňujem sa, odpoveď sa nepodarila vygenerovať."

        return jsonify({"response": text})

    except Exception as e:
        print("CHAT ERROR:", repr(e))
        return jsonify({"response": "Nastala chyba servera. Skús to prosím o chvíľu."})


if __name__ == "__main__":
    # Lokálne spúšťanie (na Render to beží cez gunicorn)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
