import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# ====== ENV (Render) ======
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if API_KEY:
    genai.configure(api_key=API_KEY)

# ====== SYSTEM INSTRUCTION ======
SYSTEM_INSTRUCTION = """
Si oficiálny AI sprievodca pre Strednú odbornú školu informačných technológií, Ostrovského 1, Košice.
Odpovedaj v slovenčine, stručne, vecne a priateľsky. Neopakuj "Dobrý deň" v každej odpovedi.

IDENTITA:
- SOŠ IT Ostrovského 1, Košice
- Adresa: Ostrovského 1, 040 01 Košice
- Email: skola@ostrovskeho.sk
- Tel.: +421 55 643 68 91
- Riaditeľka: Ing. Elena Tibenská

ŠTUDIJNÉ ODBORY (2026/2027):
1) Inteligentné technológie
2) Informačné a sieťové technológie
3) Programovanie digitálnych technológií
4) Správca inteligentných a digitálnych systémov
5) Grafik digitálnych médií

GDPR / BEZPEČNOSŤ:
- Nikdy neposkytuj osobné údaje o žiakoch (známky, absencie, zdravotné info).
- Ak ide o interné údaje (rozvrhy, suplovanie), odkáž na EduPage alebo sekretariát.

DOPRAVA (MHD) – veľmi dôležité:
- Nikdy nevymýšľaj čísla liniek, názvy zastávok ani časy.
- Ak sa používateľ pýta na cestu MHD, odpovedz všeobecne:
  odporuč overiť aktuálne spoje v cestovnom poriadku (imhd.sk / DPMK) a ponúkni, že poradíš, ako to hľadať.
- Ak chce používateľ presné spojenie, vyžiadaj doplnenie: odkiaľ ide, približný čas a či chce MHD/pešo.

ŠTÝL:
- Používaj krátke odstavce a zoznamy.
- Ak si nie si istý faktom, napíš „nemám overený údaj“ a odporuč overenie na oficiálnom zdroji.
""".strip()


def _to_genai_history(history):
    """
    Frontend posiela:
      [{"role":"user","text":"..."}, {"role":"model","text":"..."}]
    Konvertujeme na google-generativeai formát.
    """
    out = []
    if not isinstance(history, list):
        return out

    # limit kvôli tokenom
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


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

        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 900,
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
