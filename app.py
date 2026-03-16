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

# ===== SYSTEM PROMPT =====
SYSTEM_INSTRUCTION = """
Si AI sprievodca pre SOŠ IT Ostrovského 1, Košice.

Tvoja úloha je pomáhať LEN s témami súvisiacimi so školou.
Povoľené témy:
- študijné odbory
- prijímačky
- podmienky štúdia
- kontakty na školu
- adresa školy
- doprava do školy
- všeobecné informácie o škole
- štúdium pre uchádzačov
- základné organizačné informácie

Dôležité pravidlá:
- Ak otázka NESÚVISÍ so školou, slušne odmietni odpovedať.
- Pri nesúvisiacich otázkach nevysvetľuj tému a nedávaj normálnu odpoveď.
- Namiesto toho povedz, že si AI sprievodca školy a pomáhaš len s otázkami o škole SOŠ IT Ostrovského.
- Potom používateľa jemne nasmeruj späť na tému školy.

Príklady otázok, na ktoré NEMÁŠ odpovedať:
- šport
- celebrity
- politika
- vtipy
- emoji
- programovanie mimo kontextu školy
- všeobecné encyklopedické otázky
- porovnávanie Ronaldo vs Messi
- náhodné testovanie AI

Štýl odpovedí:
- odpovedaj po slovensky
- stručne, jasne a priateľsky
- keď je to vhodné, použi odrážky
- nevymýšľaj si informácie
- ak si si neistý, povedz to otvorene

GDPR:
- Neposkytuj osobné údaje o žiakoch.
- Pri interných veciach (rozvrh, suplovanie, známky) odporuč EduPage alebo sekretariát.

DOPRAVA:
- Nikdy nevymýšľaj čísla liniek, názvy zastávok ani časy.
- Pri otázkach na cestu odporuč overiť aktuálne spoje cez imhd.sk alebo DPMK.

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
    return ("ResourceExhausted" in msg) or ("Quota exceeded" in msg) or ("429" in msg)


def _retry_seconds(msg: str):
    m = re.search(r"Please retry in ([0-9.]+)s", msg)
    if not m:
        return None
    sec = int(float(m.group(1)))
    return max(5, min(sec, 180))


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _is_school_related(message: str) -> bool:
    text = _normalize_text(message)

    school_keywords = [
        "škola", "sos it", "soš it", "ostrovskeho", "ostrovského",
        "odbor", "odbory", "štúdium", "studium", "študovať", "studovat",
        "prijímačky", "prijimacky", "prijatie", "uchádzač", "uchadzac",
        "kontakt", "telefón", "telefon", "email", "mail", "sekretariát", "sekretariat",
        "adresa", "kde sa nachádza", "kde je škola", "kde je skola",
        "internát", "internat", "doprava", "mhd", "autobus", "električka", "elektricka",
        "grafik", "programovanie", "sieťové", "sietove", "digitálnych", "digitalnych",
        "inteligentné technológie", "inteligentne technologie",
        "správca inteligentných a digitálnych systémov",
        "spravca inteligentnych a digitalnych systemov",
        "podmienky prijatia", "deň otvorených dverí", "den otvorenych dveri",
        "maturita", "rozvrh", "edupage", "vyučovanie", "vyucovanie"
    ]

    offtopic_keywords = [
        "ronaldo", "messi", "futbal", "seahorse", "emoji", "vtip", "meme",
        "politika", "prezident", "vojna", "bitcoin", "kryptomeny",
        "film", "seriál", "serial", "herec", "celebrita", "youtuber",
        "počasie", "pocasie", "recept", "hra", "minecraft", "fortnite"
    ]

    if any(word in text for word in school_keywords):
        return True

    if any(word in text for word in offtopic_keywords):
        return False

    # veľmi krátke testovacie / nezmyselné otázky
    nonsense_patterns = [
        r"nap[ií]š emoji",
        r"napis emoji",
        r"daj emoji",
        r"kto je lep[sš]í",
        r"kto je lepsi",
        r"povedz vtip",
        r"nap[ií]š vtip",
        r"ako sa m[aá][sš]",
        r"si tam",
        r"hello",
        r"hi$",
        r"test$",
        r"123+$"
    ]

    if any(re.search(pattern, text) for pattern in nonsense_patterns):
        return False

    # otázky typu "môžem ísť na túto školu", "aké sú podmienky", "je možné študovať"
    school_question_patterns = [
        r"m[oô][žz]em .* (na|do) .* [šs]kol",
        r"ako sa .* prihl[aá]si",
        r"ak[eé] s[uú] podmienky",
        r"je mo[zž]n[eé] [šs]tudova",
        r"chcem [šs]tudova",
        r"zauj[ií]ma ma [šs]t[uú]dium",
        r"what.*school",
        r"study.*school",
        r"admission",
        r"apply"
    ]

    if any(re.search(pattern, text) for pattern in school_question_patterns):
        return True

    return False


def _offtopic_reply():
    return (
        "Som AI sprievodca pre SOŠ IT Ostrovského, takže pomáham len s otázkami o škole, "
        "študijných odboroch, prijímačkách, kontaktoch alebo štúdiu. "
        "Skús sa ma prosím opýtať niečo o škole 🙂"
    )


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

        # ===== TVRDÝ FILTER NA OFF-TOPIC =====
        if not _is_school_related(message):
            return jsonify({"response": _offtopic_reply()})

        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.25,
                "max_output_tokens": 700,
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

        if _is_busy_error(msg):
            sec = _retry_seconds(msg)
            if sec:
                return jsonify({"response": f"Momentálne je veľa ľudí naraz. Skús to prosím o {sec} sekúnd."})
            return jsonify({"response": "Momentálne je veľa ľudí naraz. Skús to prosím o chvíľu."})

        return jsonify({"response": "Nastala chyba servera. Skús to prosím o chvíľu."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
