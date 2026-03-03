import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if API_KEY:
    genai.configure(api_key=API_KEY)

SYSTEM_INSTRUCTION = """
Si oficiálny AI sprievodca pre SOŠ IT Ostrovského 1, Košice.

ODPOVEDE:
- Odpovedaj stručne, jasne a profesionálne.
- Nepíš "Dobrý deň" pri každej odpovedi.
- Používaj odrážky pri zoznamoch.
- Ak si nie si istý faktom, napíš: "Nemám overený údaj."

DOPRAVA (MHD):
- Nikdy nevymýšľaj čísla liniek ani názvy zastávok.
- Neuvádzaj konkrétne spoje ani časy.
- Pri otázke na cestu odporuč overiť aktuálne spoje na imhd.sk alebo DPMK.
- Ak chce presné spojenie, vyžiadaj doplnenie (odkiaľ, kam, približný čas).

GDPR:
- Neposkytuj osobné údaje o žiakoch.
- Interné informácie (rozvrh, suplovanie) → odkáž na EduPage.

ŠKOLA:
SOŠ IT Ostrovského 1, Košice
Email: skola@ostrovskeho.sk
Tel.: +421 55 643 68 91

Študijné odbory (2026/2027):
1. Inteligentné technológie
2. Informačné a sieťové technológie
3. Programovanie digitálnych technológií
4. Správca inteligentných a digitálnych systémov
5. Grafik digitálnych médií
""".strip()


def convert_history(history):
    formatted = []
    if not isinstance(history, list):
        return formatted

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


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        history = data.get("history", [])

        if not message:
            return jsonify({"response": "Napíš prosím otázku 🙂"})

        if not API_KEY:
            return jsonify({"response": "Server nie je správne nakonfigurovaný."})

        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 800
            },
        )

        chat = model.start_chat(history=convert_history(history))
        response = chat.send_message(message)

        text = (response.text or "").strip()
        if not text:
            text = "Ospravedlňujem sa, odpoveď sa nepodarila vygenerovať."

        return jsonify({"response": text})

    except Exception as e:
        print("ERROR:", repr(e))
        return jsonify({"response": "Veľa aktívnych použivateľov. Skús to prosím o chvíľu."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
