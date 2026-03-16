import os
import re
import html
import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
MODEL_NAME = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()

if API_KEY:
    genai.configure(api_key=API_KEY)

SYSTEM_INSTRUCTION = """
Si AI sprievodca pre SOŠ IT Ostrovského v Košiciach.

Pravidlá:
- Odpovedaj LEN na témy súvisiace so školou.
- Odpovedaj po slovensky, stručne, jasne a priateľsky.
- Odpovedaj iba na základe dodaného kontextu zo školských zdrojov.
- Ak v kontexte nie je odpoveď, povedz, že si to nevieš overiť a odporuč školský web alebo EduPage.
- Nevymýšľaj si fakty.
- Nepíš nič o témach mimo školy.
- Ak je otázka mimo školy, slušne odmietni a presmeruj používateľa späť na školu.

GDPR:
- Neposkytuj osobné údaje o žiakoch.
- Pri interných veciach ako známky, rozvrh, suplovanie alebo dochádzka odporuč EduPage alebo sekretariát.

DOPRAVA:
- Nikdy nevymýšľaj čísla liniek, názvy zastávok ani časy.
- Pri otázkach na cestu odporuč overiť aktuálne spoje.
""".strip()

# Povolené školské zdroje
SOURCE_URLS = {
    "school_home": "https://ostrovskeho.com/",
    "school_contacts": "https://ostrovskeho.sk/index.php?id=studium&page=technicke_lyceum2",
    "edupage_home": "https://ostrov.edupage.org/",
    "edupage_login": "https://ostrov.edupage.org/login/",
    "edupage_menu": "https://ostrov.edupage.org/menu/",
    "dod_home": "https://www.dod.sos-ostrovskeho.sk/",
}

ALLOWED_DOMAINS = {
    "ostrovskeho.com",
    "www.ostrovskeho.com",
    "ostrovskeho.sk",
    "www.ostrovskeho.sk",
    "ostrov.edupage.org",
    "dod.sos-ostrovskeho.sk",
    "www.dod.sos-ostrovskeho.sk",
}

# Základná overená knowledge base
STATIC_KB = [
    {
        "patterns": [
            r"\bkontakt\b", r"\bkontakty\b", r"\bemail\b", r"\be-mail\b",
            r"\bmail\b", r"\btelef[oó]n\b", r"\badresa\b", r"\bsekretari[aá]t\b"
        ],
        "answer": (
            "Kontakt na školu:\n"
            "- Adresa: Ostrovského 1, 040 01 Košice\n"
            "- Email: skola@ostrovskeho.sk\n"
            "- Telefón: +421 55 643 68 91\n\n"
            "Ak chceš, môžem ti poradiť aj s odbormi, prijímačkami alebo EduPage."
        )
    },
    {
        "patterns": [
            r"jed[aá]l", r"strav", r"obed", r"obed[y]?", r"jed[aá]lny l[ií]stok", r"menu"
        ],
        "answer": (
            "Jedálny lístok nájdeš na EduPage školy v sekcii Jedálny lístok.\n"
            "Ak chceš, môžem ti poradiť aj s ďalšími informáciami o škole alebo kde hľadať konkrétne sekcie na EduPage."
        )
    },
    {
        "patterns": [
            r"edupage", r"zn[aá]mky", r"doch[aá]dzk", r"prihl[aá]s", r"rozvrh", r"suplovanie"
        ],
        "answer": (
            "Na známky, dochádzku, rozvrh, suplovanie a prihlasovanie odporúčam EduPage školy. "
            "Ak chceš, môžem ti poradiť, kde tam hľadať konkrétnu sekciu."
        )
    },
]

OFFTOPIC_PATTERNS = [
    r"\bronald[o]?\b", r"\bmessi\b", r"\bfutbal\b", r"\bseahorse\b", r"\bemoji\b",
    r"\bvtip\b", r"\bmeme\b", r"\bpolitika\b", r"\bprezident\b", r"\bvojna\b",
    r"\bbitcoin\b", r"\bkrypto\b", r"\bfilm\b", r"\bseri[aá]l\b", r"\bpo[cč]asie\b",
    r"\bminecraft\b", r"\bfortnite\b", r"\bako sa m[aá][sš]\b"
]

SCHOOL_PATTERNS = [
    r"\bškola\b", r"\bskola\b", r"\bsoš\b", r"\bsos\b", r"\bostrovsk", r"\bodbor",
    r"\bodbory\b", r"\bšt[uú]d", r"\bstud", r"\bprij[ií]ma[cč]", r"\buch[aá]dza[cč]",
    r"\bkontakt", r"\bmail\b", r"\bemail\b", r"\btelef[oó]n\b", r"\badresa\b",
    r"\bedupage\b", r"\bjed[aá]l", r"\bstrav", r"\bobed", r"\bintern[aá]t\b",
    r"\bdoprava\b", r"\bmhd\b", r"\bko[sš]ice\b", r"\bmaturit", r"\bvyu[cč]ovanie\b",
    r"\bgrafik\b", r"\bprogramovanie\b", r"\bsie[tť]ov", r"\binteligentn"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SOS-IT-chatbot/1.0)"
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_offtopic(message: str) -> bool:
    text = normalize_text(message)
    return any(re.search(p, text) for p in OFFTOPIC_PATTERNS)


def is_school_related(message: str) -> bool:
    text = normalize_text(message)

    if is_offtopic(text):
        return False

    if any(re.search(p, text) for p in SCHOOL_PATTERNS):
        return True

    # hraničné otázky po anglicky
    english_school_patterns = [
        r"\bschool\b", r"\badmission\b", r"\bstudy\b", r"\bcanteen\b", r"\blunch\b",
        r"\bmenu\b", r"\bcontact\b", r"\bsubjects\b", r"\bdepartment\b", r"\bmajor\b"
    ]
    if any(re.search(p, text) for p in english_school_patterns):
        return True

    return False


def offtopic_reply() -> str:
    return (
        "Som AI sprievodca pre SOŠ IT Ostrovského, takže pomáham len s otázkami o škole, "
        "študijných odboroch, prijímačkách, kontaktoch, EduPage alebo štúdiu. "
        "Skús sa ma prosím opýtať niečo o škole 🙂"
    )


def static_kb_answer(message: str):
    text = normalize_text(message)
    for item in STATIC_KB:
        for pattern in item["patterns"]:
            if re.search(pattern, text):
                return item["answer"]
    return None


def choose_source_urls(message: str):
    text = normalize_text(message)
    urls = []

    # jedáleň / menu / obedy
    if re.search(r"jed[aá]l|strav|obed|menu", text):
        urls.extend([
            SOURCE_URLS["edupage_menu"],
            SOURCE_URLS["edupage_home"],
            SOURCE_URLS["school_home"],
        ])

    # EduPage / interné veci
    elif re.search(r"edupage|zn[aá]mky|doch[aá]dzk|rozvrh|suplovanie|prihl[aá]s", text):
        urls.extend([
            SOURCE_URLS["edupage_login"],
            SOURCE_URLS["edupage_home"],
            SOURCE_URLS["school_home"],
        ])

    # kontakty
    elif re.search(r"kontakt|mail|email|telef[oó]n|adresa|sekretari[aá]t", text):
        urls.extend([
            SOURCE_URLS["school_contacts"],
            SOURCE_URLS["school_home"],
        ])

    # prijímačky / odbory / štúdium / uchádzači
    elif re.search(r"prij[ií]ma[cč]|uch[aá]dza[cč]|odbor|št[uú]d|stud|maturit|grafik|programovanie|sie[tť]ov|inteligentn", text):
        urls.extend([
            SOURCE_URLS["school_home"],
            SOURCE_URLS["dod_home"],
            SOURCE_URLS["school_contacts"],
        ])

    else:
        urls.extend([
            SOURCE_URLS["school_home"],
            SOURCE_URLS["school_contacts"],
            SOURCE_URLS["edupage_home"],
        ])

    # odstránenie duplicit
    out = []
    for u in urls:
        if u not in out:
            out.append(u)
    return out


def fetch_page_text(url: str) -> str:
    try:
        parsed = urlparse(url)
        if parsed.netloc not in ALLOWED_DOMAINS:
            return ""

        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        text = html.unescape(text)
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if len(line) >= 4]

        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{2,}", "\n", cleaned).strip()
        return cleaned

    except Exception as e:
        logging.warning("FETCH ERROR %s | %s", url, repr(e))
        return ""


def tokenize(text: str):
    text = normalize_text(text)
    words = re.findall(r"[a-zA-Záäčďéíĺľňóôŕšťúýž0-9]+", text)
    stop = {
        "a", "aj", "ale", "alebo", "ako", "ak", "aby", "do", "je", "na", "o", "od", "po",
        "sa", "si", "som", "sú", "su", "to", "ten", "tá", "ta", "toho", "tej", "pre", "pri",
        "z", "zo", "u", "v", "vo", "k", "ku", "či", "co", "čo", "kde", "ako", "ktorý", "ktory",
        "ktorá", "ktora", "which", "what", "how", "where", "the", "and", "for"
    }
    return [w for w in words if len(w) > 2 and w not in stop]


def chunk_text(text: str, max_chars: int = 900):
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 1 <= max_chars:
            current = f"{current}\n{p}".strip()
        else:
            if current:
                chunks.append(current)
            current = p

    if current:
        chunks.append(current)

    return chunks


def retrieve_context(question: str):
    urls = choose_source_urls(question)
    q_tokens = set(tokenize(question))
    scored = []

    for url in urls:
        page_text = fetch_page_text(url)
        if not page_text:
            continue

        for chunk in chunk_text(page_text):
            c_tokens = set(tokenize(chunk))
            overlap = len(q_tokens & c_tokens)

            bonus = 0
            q = normalize_text(question)
            c = normalize_text(chunk)

            if "jedáln" in q or "jedaln" in q or "obed" in q:
                if "jedálny lístok" in c or "menu" in c or "obed" in c:
                    bonus += 4

            if "kontakt" in q or "email" in q or "telef" in q or "adresa" in q:
                if "kontakt" in c or "email" in c or "tel." in c or "ostrovského 1" in c:
                    bonus += 4

            if "prij" in q or "uchádzač" in q or "uchadzac" in q or "odbor" in q:
                if "odbor" in c or "prijímacie" in c or "štúdium" in c or "študijné" in c:
                    bonus += 3

            score = overlap + bonus
            if score > 0:
                scored.append((score, url, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    top = []
    seen_chunks = set()

    for score, url, chunk in scored:
        key = chunk[:200]
        if key in seen_chunks:
            continue
        seen_chunks.add(key)
        top.append((url, chunk))
        if len(top) >= 5:
            break

    return top


def build_context_block(retrieved):
    if not retrieved:
        return ""

    parts = []
    for i, (url, chunk) in enumerate(retrieved, start=1):
        parts.append(f"[ZDROJ {i}] {url}\n{chunk}")
    return "\n\n".join(parts)


def build_prompt(question: str, context_block: str) -> str:
    return f"""
{SYSTEM_INSTRUCTION}

Používateľova otázka:
{question}

Overený kontext zo školských zdrojov:
{context_block}

Pokyny pre odpoveď:
- Odpovedz iba z kontextu vyššie.
- Ak sa odpoveď dá podať stručne, buď stručný.
- Ak ide o navigáciu na školský web alebo EduPage, povedz používateľovi, kde to nájde.
- Ak v kontexte nie je presná odpoveď, povedz to otvorene.
- Neodpovedaj na nič mimo školy.
""".strip()


def gemini_answer(prompt: str) -> str:
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 700,
        },
    )

    resp = model.generate_content(prompt)
    text = (getattr(resp, "text", "") or "").strip()

    if text:
        return text

    # fallback pre candidates
    try:
        candidates = getattr(resp, "candidates", None)
        if candidates:
            chunks = []
            for c in candidates:
                content = getattr(c, "content", None)
                if not content:
                    continue
                for p in getattr(content, "parts", []) or []:
                    part_text = getattr(p, "text", None)
                    if part_text:
                        chunks.append(part_text.strip())
            joined = "\n".join([x for x in chunks if x]).strip()
            if joined:
                return joined
    except Exception:
        pass

    return ""


def fallback_school_reply(message: str) -> str:
    text = normalize_text(message)

    if re.search(r"jed[aá]l|strav|obed|menu", text):
        return (
            "Jedálny lístok nájdeš na EduPage školy v sekcii Jedálny lístok. "
            "Ak chceš, môžem ti pomôcť aj s ďalšími informáciami o škole."
        )

    if re.search(r"edupage|zn[aá]mky|doch[aá]dzk|rozvrh|suplovanie", text):
        return (
            "Na tieto informácie odporúčam EduPage školy. "
            "Ak chceš, môžem ti poradiť, kde tam hľadať konkrétnu sekciu."
        )

    if re.search(r"kontakt|mail|email|telef[oó]n|adresa", text):
        return (
            "Kontakt na školu je:\n"
            "- Adresa: Ostrovského 1, 040 01 Košice\n"
            "- Email: skola@ostrovskeho.sk\n"
            "- Telefón: +421 55 643 68 91"
        )

    return (
        "Pomáham s otázkami o SOŠ IT Ostrovského. "
        "Ak chceš, opýtaj sa ma na odbory, prijímačky, kontakty, EduPage alebo informácie o škole."
    )


def _is_busy_error(msg: str) -> bool:
    msg = msg or ""
    return ("ResourceExhausted" in msg) or ("Quota exceeded" in msg) or ("429" in msg)


def _retry_seconds(msg: str):
    m = re.search(r"Please retry in ([0-9.]+)s", msg or "")
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

        if not message:
            return jsonify({"response": "Napíš prosím otázku 🙂"})

        if not API_KEY:
            return jsonify({"response": "Služba je momentálne nedostupná. Skús to prosím neskôr."})

        if not is_school_related(message):
            return jsonify({"response": offtopic_reply()})

        # rýchle odpovede na jasné školské otázky
        static_answer = static_kb_answer(message)
        if static_answer:
            return jsonify({"response": static_answer})

        retrieved = retrieve_context(message)
        context_block = build_context_block(retrieved)

        if not context_block:
            return jsonify({"response": fallback_school_reply(message)})

        prompt = build_prompt(message, context_block)
        text = gemini_answer(prompt)

        if not text:
            text = fallback_school_reply(message)

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
