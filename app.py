import os
import re
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if API_KEY:
    genai.configure(api_key=API_KEY)

SYSTEM_INSTRUCTION = """
Si oficiálny AI sprievodca pre SOŠ IT Ostrovského 1, Košice.

Odpovedaj v slovenčine, priateľsky a užitočne.
Používaj odrážky, keď je to vhodné.
Nepožaduj zbytočné spresnenia, ak vieš odpovedať z kontextu.

GDPR:
- Neposkytuj osobné údaje o žiakoch.
- Ak ide o interné veci (rozvrh, suplovanie), odkáž na EduPage alebo sekretariát.

DOPRAVA (MHD):
- Nikdy nevymýšľaj čísla liniek, názvy zastávok ani časy.
- Ak sa používateľ pýta na spoje, odpovedz všeobecne a odporuč overiť aktuálne spoje na imhd.sk / DPMK.
- Môžeš poradiť, ako si spoj vyhľadať, a spýtať sa na doplnenie (odkiaľ, približný čas), ak treba.

ŠKOLA:
SOŠ IT Ostrovského 1, Košice
Email: skola@ostrovskeho.sk
Tel.: +421 55 643 68 91

Študijné odbory (2026/2027):
1) Inteligentné technológie
2) Informačné a sieťové technológie
3) Programovanie digitálnych technológií
4) Správca inteligentných a digitálnych systémov
5) Grafik digitálnych médií
""".strip()


def convert_history(history):
    formatted = []
    if not isinstance(history, list):
        return formatted

    # necháme viac kontextu (lepšie odpovede)
    history = history[-12:]

    for msg in history:
        role = msg.get("role")
        text = (msg.get("text") or "").strip()
        if not text:
            continue

        if role == "user":
            formatted.append({"role": "user", "parts": [text]})
        else:
            formatted.append({"role": "model", "parts": [text]})

    return formatted


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
                "temperature": 0.45,
                "max_output_tokens": 900,   # kvalita/obsah späť
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

        # Rate limit / quota -> nenápadná hláška
        if ("ResourceExhausted" in msg) or ("Quota exceeded" in msg) or ("429" in msg):
            m = re.search(r"Please retry in ([0-9.]+)s", msg)
            if m:
                sec = int(float(m.group(1)))
                sec = max(5, min(sec, 180))
                return jsonify({"response": f"Momentálne je veľa ľudí naraz. Skús to prosím o {sec} sekúnd."})
            return jsonify({"response": "Momentálne je veľa ľudí naraz. Skús to prosím o chvíľu."})

        return jsonify({"response": "Nastala chyba servera. Skús to prosím o chvíľu."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
