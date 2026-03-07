import os
import re
import logging
import traceback
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ===== ENV =====
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    logging.warning("GEMINI_API_KEY nie je nastavený.")

# ===== SYSTEM PROMPT =====
SYSTEM_INSTRUCTION = """
Si AI sprievodca pre SOŠ IT Ostrovského 1, Košice.
Odpovedaj v slovenčine, priateľsky a užitočne. Keď je to vhodné, použi odrážky.

GDPR:
- Neposkytuj osobné údaje o žiakoch.
- Pri interných veciach (rozvrh, suplovanie) odporuč EduPage alebo sekretariát.

DOPRAVA (MHD):
- Nikdy nevymýšľaj čísla liniek, názvy zastávok ani časy.
- Pri otázkach na cestu odporuč overiť aktuálne spoje v cestovnom poriadku (imhd.sk / DPMK).

Ak si nie si istý odpoveďou, povedz to otvorene a odporuč kontaktovať školu.

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
    """
    Frontend posiela:
    [{"role":"user|model","text":"..."}]
    """
    out = []

    if not isinstance(history, list):
        return out

    # obmedzenie histórie, aby request nebol zbytočne veľký
    history = history[-12:]

    for item in history:
        if not isinstance(item, dict):
            continue

        role = (item.get("role") or "").strip().lower()
        text = (item.get("text") or "").strip()

        if not text:
            continue

        if role == "user":
            out.append({
                "role": "user",
                "parts": [{"text": text}]
            })
        elif role in ("model", "assistant"):
            out.append({
                "role": "model",
                "parts": [{"text": text}]
            })

    return out


def _is_busy_error(msg: str) -> bool:
    msg_lower = (msg or "").lower()
    busy_markers = [
        "resourceexhausted",
        "quota exceeded",
        "429",
        "rate limit",
        "too many requests"
    ]
    return any(marker in msg_lower for marker in busy_markers)


def _is_api_key_error(msg: str) -> bool:
    msg_lower = (msg or "").lower()
    markers = [
        "api key not valid",
        "invalid api key",
        "permission denied",
        "authentication",
        "unauthorized",
        "403"
    ]
    return any(marker in msg_lower for marker in markers)


def _retry_seconds(msg: str):
    if not msg:
        return None

    patterns = [
        r"Please retry in ([0-9.]+)s",
        r"retry in ([0-9.]+)s",
        r"retry_delay.*?seconds: ([0-9.]+)"
    ]

    for pattern in patterns:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            try:
                sec = int(float(m.group(1)))
                return max(5, min(sec, 180))
            except Exception:
                return None

    return None


def _extract_response_text(resp):
    """
    Bezpečné vytiahnutie textu z Gemini odpovede.
    """
    if resp is None:
        return ""

    # 1. Najskôr skús priamo .text
    try:
        text = getattr(resp, "text", "")
        if text and str(text).strip():
            return str(text).strip()
    except Exception:
        pass

    # 2. Skús prejsť candidates/content/parts
    try:
        candidates = getattr(resp, "candidates", None)
        if candidates:
            chunks = []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                if not content:
                    continue

                parts = getattr(content, "parts", None)
                if not parts:
                    continue

                for part in parts:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        chunks.append(str(part_text).strip())

            joined = "\n".join([c for c in chunks if c])
            if joined.strip():
                return joined.strip()
    except Exception:
        pass

    return ""


def _get_model():
    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config={
            "temperature": 0.35,
            "max_output_tokens": 700,
            "top_p": 0.9,
            "top_k": 40,
        },
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model": MODEL_NAME,
        "api_key_configured": bool(API_KEY)
    })


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}

        message = (data.get("message") or "").strip()
        history = data.get("history", [])

        if not message:
            return jsonify({"response": "Napíš prosím otázku 🙂"}), 400

        if len(message) > 3000:
            return jsonify({
                "response": "Otázka je príliš dlhá. Skús ju prosím trochu skrátiť."
            }), 400

        if not API_KEY:
            logging.error("Chýba GEMINI_API_KEY.")
            return jsonify({
                "response": "Služba je momentálne nedostupná. Skús to prosím neskôr."
            }), 503

        safe_history = convert_history(history)

        logging.info("CHAT request | model=%s | history_len=%s | msg_len=%s",
                     MODEL_NAME, len(safe_history), len(message))

        model = _get_model()
        chat_session = model.start_chat(history=safe_history)
        resp = chat_session.send_message(message)

        text = _extract_response_text(resp)

        if not text:
            logging.warning("Gemini vrátil prázdnu odpoveď.")
            return jsonify({
                "response": "Ospravedlňujem sa, odpoveď sa nepodarila vygenerovať. Skús otázku položiť ešte raz."
            }), 502

        return jsonify({"response": text}), 200

    except Exception as e:
        err_repr = repr(e)
        err_str = str(e)

        logging.error("CHAT ERROR: %s", err_repr)
        logging.error("TRACEBACK:\n%s", traceback.format_exc())

        if _is_api_key_error(err_str):
            return jsonify({
                "response": "Nastavenie AI služby nie je momentálne v poriadku. Skús to prosím neskôr."
            }), 503

        if _is_busy_error(err_str):
            sec = _retry_seconds(err_str)
            if sec:
                return jsonify({
                    "response": f"Momentálne je veľa požiadaviek naraz. Skús to prosím o {sec} sekúnd."
                }), 429

            return jsonify({
                "response": "Momentálne je veľa požiadaviek naraz. Skús to prosím o chvíľu."
            }), 429

        return jsonify({
            "response": "Nastala chyba servera. Skús to prosím o chvíľu."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
