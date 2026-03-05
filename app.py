from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os

import google.generativeai as genai

from cache import get_cached_answer, save_answer, normalize_question

app = Flask(__name__)
CORS(app)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")

# FAQ odpovede bez AI
FAQ = {

normalize_question("ake su odbory na skole"):
"""
Naša škola ponúka tieto študijné odbory:

* **Inteligentné technológie**
* **Informačné a sieťové technológie**
* **Programovanie digitálnych technológií**
* **Správca inteligentných a digitálnych systémov**
* **Grafik digitálnych médií**
""",

normalize_question("kontakt"):
"""
Kontaktné údaje na sekretariát:

* **Tel:** +421 55 643 68 91
* **Email:** skola@ostrovskeho.sk
""",

normalize_question("kde sa nachadza skola"):
"""
SOŠ IT Ostrovského 1 sa nachádza v **Košiciach** na adrese:

**Ostrovského 1**
"""
}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()
    question = data.get("message", "").strip()

    if not question:
        return jsonify({"reply": "Napíš prosím otázku 🙂"})


    key = normalize_question(question)


    # 1️⃣ FAQ odpoveď
    if key in FAQ:
        return jsonify({"reply": FAQ[key]})


    # 2️⃣ CACHE odpoveď
    cached = get_cached_answer(question)

    if cached:
        return jsonify({"reply": cached})


    # 3️⃣ AI odpoveď
    try:

        prompt = f"""
Si AI sprievodca pre SOŠ IT Ostrovského 1 v Košiciach.

Odpovedaj stručne, jasne a v slovenčine.

Otázka:
{question}
"""

        response = model.generate_content(prompt)

        answer = response.text.strip()


        # uložiť do cache
        save_answer(question, answer)


        return jsonify({"reply": answer})


    except Exception:

        return jsonify({
            "reply": "Momentálne je veľa ľudí naraz. Skús to prosím o chvíľu."
        })


if __name__ == "__main__":
    app.run()
