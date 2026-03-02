import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, template_folder='templates')
CORS(app)

# Konfigurácia API
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"
genai.configure(api_key=API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    tools=[{"google_search_retrieval": {}}] 
)

# Znalostná báza podľa tvojho manuálu
SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre SOŠ IT Ostrovského 1, Košice. 
Tvojou úlohou je poskytovať presné informácie na základe "Znalostného manuálu školy".

IDENTITA A KONTAKTY:
- Názov: SOŠ IT Ostrovského 1, Košice. Adresa: Ostrovského 1, 040 01 Košice.
- Kontakty: skola@ostrovskeho.sk, +421 55 643 68 91. Riaditeľka: Ing. Elena Tibenská.

ŠTUDIJNÉ ODBORY (2026/2027):
1. 2559 M Inteligentné technológie (IoT, AI, robotika, kyberbezpečnosť).
2. 2561 M Informačné a sieťové technológie (hardvér, siete, Java).
3. 2573 M Programovanie digitálnych technológií (najnáročnejší, hry, VR).
4. 2571 K Správca inteligentných a digitálnych systémov (praktický, servis, senzory).
5. 3447 K Grafik digitálnych médií (Adobe, grafika, weby).

DÔLEŽITÉ FAKTY Z MANUÁLU:
- Notebooky: Žiaci potrebujú notebook s Windows 10/11 a dedikovanou GPU (OpenGL 4.3).
- Termíny 25/26: Jarné prázdniny (Košice) 2.3. - 6.3.2026. Maturita SJL 10.3.2026.
- Internát a jedáleň: Sú súčasťou areálu školy.
- Psychológ: Miestnosť 022, pomoc pri šikane alebo problémoch.

PRAVIDLÁ:
- Ak niečo nevieš, odpovedz "nešpecifikované" a odkáž na EduPage (https://ostrov.edupage.org/).
- Dodržuj GDPR: Nikdy neposkytuj osobné údaje žiakov.
"""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get("message")
        if not user_message:
            return jsonify({"error": "No message"}), 400

        chat_session = model.start_chat(history=[])
        full_prompt = f"{SYSTEM_INSTRUCTION}\n\nOtázka používateľa: {user_message}"
        
        response = chat_session.send_message(full_prompt)
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
