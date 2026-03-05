import os
import re
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# ===== ENV =====
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if API_KEY:
    genai.configure(api_key=API_KEY)

# ===== SYSTEM PROMPT (len essentials + anti-MHD halucinácie) =====
SYSTEM_INSTRUCTION = """
Si AI sprievodca pre SOŠ IT Ostrovského 1, Košice.
Odpovedaj v slovenčine, priateľsky a užitočne. Keď je to vhodné, použi odrážky.

GDPR:
- Neposkytuj osobné údaje o žiakoch.
- Pri interných veciach (rozvrh, suplovanie) odporuč EduPage alebo sekretariát.

DOPRAVA (MHD):
- Nikdy nevymýšľaj čísla liniek, názvy zastávok ani časy.
- Pri otázkach na cestu odporuč overiť aktuálne spoje v cestovnom poriadku (imhd.sk / DPMK).

Základné info:
- Adresa: Ostrovského 1, Košice
- Email: skola@ostrovskeho.sk
- Tel.: +421 55 643 68 91

Študijné odbory:
1) Inteligentné technológie
2) Informačné a sieťové technológie
3) Programovanie digitálnych technológií
4) Správca inteligentných a digitálnych systémov
5) Grafik digitálnych médií
""".strip()


def convert_history(history):
    """Frontend posiela: [{"role":"user|model","text":"..."}]"""
    out = []
    if not isinstance(history, list):
        return out

    # necháme kontext, aby odpovede boli dobré
    history = history[-12:]

    for item in history:
        role = item.get("role")
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            out.append({"role": "user", "parts": [text]})
        else:
            out.append({"role": "model", "parts": [text]})
    return out


def _is_busy_error(msg: str) -> bool:
    # Gemini quota / rate limit typicky vyhadzuje ResourceExhausted / Quota exceeded / 429
    return ("ResourceExhausted" in msg) or ("Quota exceeded" in msg) or ("429" in msg)


def _retry_seconds(msg: str):
    m = re.search(r"Please retry in ([0-9.]+)s", msg)
    if not m:
        return None
    sec = int(float(m.group(1)))
    return max(5, min(sec, 180))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        history = data.get("history", [])

        if not message:
            return jsonify({"response": "Napíš prosím otázku 🙂"})

        if not API_KEY:
            return jsonify({"response": "Služba je momentálne nedostupná. Skús to prosím neskôr."})

        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.45,      # nech to odpovedá pekne
                "max_output_tokens": 900, # nech to nie je príliš krátke
            },
        )

        chat_session = model.start_chat(history=convert_history(history))
        resp = chat_session.send_message(message)

        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            text = "Ospravedlňujem sa, odpoveď sa nepodarila vygenerovať."
        return jsonify({"response": text})

    except Exception as e:
        print("CHAT ERROR:", repr(e))
        msg = str(e)

        # Nenápadná hláška pri vyťažení/limite
        if _is_busy_error(msg):
            sec = _retry_seconds(msg)
            if sec:
                return jsonify({"response": f"Momentálne je veľa ľudí naraz. Skús to prosím o {sec} sekúnd."})
            return jsonify({"response": "Momentálne je veľa ľudí naraz. Skús to prosím o chvíľu."})

        return jsonify({"response": "Nastala chyba servera. Skús to prosím o chvíľu."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
