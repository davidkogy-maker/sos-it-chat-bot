import os
import time
import re
import threading
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# ====== ENV (Render) ======
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # nechaj ako máš

if API_KEY:
    genai.configure(api_key=API_KEY)

# ====== SOFT LIMITING (aby free tier lepšie zvládal viac ľudí) ======
# Minimálny odstup medzi správami z jednej IP (sekundy)
PER_IP_COOLDOWN_SECONDS = 2.5

# Max paralelných volaní do Gemini (na free Render + free tier je lepšie 1)
MAX_CONCURRENT_CALLS = 1
_sema = threading.Semaphore(MAX_CONCURRENT_CALLS)

# IP -> last_time
_last_req = {}
_last_req_lock = threading.Lock()

def _client_ip():
    # Render často posiela X-Forwarded-For
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"

def _too_soon(ip: str) -> float:
    """Vracia koľko sekúnd ešte má čakať, alebo 0 ak môže pokračovať."""
    now = time.time()
    with _last_req_lock:
        last = _last_req.get(ip, 0.0)
        wait = (last + PER_IP_COOLDOWN_SECONDS) - now
        if wait <= 0:
            _last_req[ip] = now
            return 0.0
        return wait

# ====== SYSTEM INSTRUCTION ======
SYSTEM_INSTRUCTION = """
Si oficiálny AI sprievodca pre SOŠ IT Ostrovského 1, Košice.

ODPOVEDE:
- Odpovedaj stručne, jasne a priateľsky.
- Nepíš "Dobrý deň" pri každej odpovedi.
- Používaj krátke odstavce a zoznamy.
- Ak si nie si istý faktom, napíš: "Nemám overený údaj" a odporuč overenie na oficiálnom zdroji.

DOPRAVA (MHD):
- Nikdy nevymýšľaj čísla liniek, názvy zastávok ani časy.
- Pri otázke na cestu odporuč overiť aktuálne spoje v cestovnom poriadku (imhd.sk / DPMK).
- Ak chce používateľ presné spojenie, vyžiadaj doplnenie: odkiaľ ide, približný čas, či chce MHD/pešo.

GDPR:
- Neposkytuj osobné údaje o žiakoch.
- Interné informácie (rozvrh, suplovanie) → odkáž na EduPage alebo sekretariát.

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
    """
    Frontend posiela:
      [{"role":"user","text":"..."}, {"role":"model","text":"..."}]
    Konvertujeme na google-generativeai formát.
    """
    formatted = []
    if not isinstance(history, list):
        return formatted

    # menej histórie = menej tokenov = menej zaťaženia, ale stále dosť na kontext
    history = history[-8:]

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

        # 1) per-IP cooldown
        ip = _client_ip()
        wait = _too_soon(ip)
        if wait > 0:
            return jsonify({"response": f"Prosím chvíľku počkaj a skús to znova (cca {int(wait)+1} s)."})
        
        # 2) jemné obmedzenie paralelných requestov
        acquired = _sema.acquire(timeout=5)
        if not acquired:
            return jsonify({"response": "Momentálne je veľa ľudí naraz. Skús to prosím o pár sekúnd."})

        try:
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                system_instruction=SYSTEM_INSTRUCTION,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 650,   # stále pekné odpovede, ale nie extrémne dlhé
                },
            )

            chat_session = model.start_chat(history=convert_history(history))
            resp = chat_session.send_message(message)

            text = (getattr(resp, "text", "") or "").strip()
            if not text:
                text = "Ospravedlňujem sa, odpoveď sa nepodarila vygenerovať."

            return jsonify({"response": text})

        finally:
            _sema.release()

    except Exception as e:
        # Log pre teba
        print("CHAT ERROR:", repr(e))
        msg = str(e)

        # Ak je to vyťaženie/quota/429, nehovoríme o API – iba že je veľa ľudí
        if ("ResourceExhausted" in msg) or ("Quota exceeded" in msg) or ("429" in msg):
            # vytiahneme odporúčaný retry čas, ak je dostupný
            m = re.search(r"Please retry in ([0-9.]+)s", msg)
            if m:
                sec = int(float(m.group(1)))
                sec = max(5, min(sec, 120))
                return jsonify({"response": f"Momentálne je veľa ľudí naraz. Skús to prosím o {sec} sekúnd."})
            return jsonify({"response": "Momentálne je veľa ľudí naraz. Skús to prosím o chvíľu."})

        return jsonify({"response": "Nastala chyba servera. Skús to prosím o chvíľu."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
