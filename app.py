import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app) # Dôležité pre správne fungovanie iframe v 3DVista

# --- KONFIGURÁCIA API ---
# Tvoj kľúč, ktorý si poskytol
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"
genai.configure(api_key=API_KEY)

# Nastavenie modelu s nástrojom Google Search (Hybridný systém)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    tools=[{"google_search_retrieval": {}}] 
)

# --- ZNALOSTNÁ BÁZA (podľa manuálu) ---
SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre Strednú odbornú školu informačných technológií, Ostrovského 1, Košice.
Tvojou úlohou je poskytovať presné informácie na základe "Znalostného manuálu školy".

IDENTITA A KONTAKTY:
- Názov: SOŠ IT Ostrovského 1, Košice. [cite: 39]
- Adresa: Ostrovského 1, 040 01 Košice. [cite: 39]
- Kontakty: skola@ostrovskeho.sk, +421 55 643 68 91. [cite: 41]
- Vedenie: Riaditeľka Ing. Elena Tibenská. [cite: 81]
- IČO: 00893331. [cite: 43]
- Zriaďovateľ: Košický samosprávny kraj (KSK). [cite: 73]

ŠTUDIJNÉ ODBORY (2026/2027): [cite: 98]
1. 2559 M Inteligentné technológie: IoT, AI, robotika, kybernetická bezpečnosť. [cite: 106]
2. 2561 M Informačné a sieťové technológie: hardvér, siete, OS, Java. [cite: 116, 117]
3. 2573 M Programovanie digitálnych technológií: frontend/backend, hry, VR/3D. [cite: 123]
4. 2571 K Správca inteligentných a digitálnych systémov: montáž, senzory, diagnostika. [cite: 131]
5. 3447 K Grafik digitálnych médií: digitálne médiá, Adobe balík, webstránky. [cite: 142]

DÔLEŽITÉ TERMÍNY (2025/2026): [cite: 7, 155]
- Začiatok vyučovania: 1. 9. 2025. [cite: 156]
- Koniec 1. polroka: 30. 1. 2026. [cite: 158]
- Jarné prázdniny (Košický kraj): 2. 3. 2026 – 6. 3. 2026. [cite: 160]
- Maturita (SJL/AJ): 10. 3. a 11. 3. 2026. [cite: 166]

BEZPEČNOSŤ A GDPR:
- NIKDY neposkytuj osobné údaje o žiakoch (známky, absencie, disciplinárne konania). [cite: 226, 309]
- Ak informáciu nevieš alebo je interná (rozvrhy, suplovanie), odpovedz "nešpecifikované" a odkáž na sekretariát alebo EduPage (https://ostrov.edupage.org/). [cite: 25, 301]
- Pri krízových situáciách (šikana, duševné zdravie) ponúkni kontakty na školského psychológa (miestnosť 022) alebo linky IPčko/Nezábudka. [cite: 192, 313, 314]

KOMUNIKÁCIA:
- Odpovedaj profesionálne, moderne a priateľsky. [cite: 69]
- Vždy uvádzaj, že informácie sú platné k školskému roku 2025/2026 alebo 2026/2027. [cite: 22]
"""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_data = request.json
        user_message = user_data.get("message")

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # Spustenie chatu s kontextom
        chat_session = model.start_chat(history=[])
        
        # Spojenie inštrukcií s otázkou
        full_prompt = f"{SYSTEM_INSTRUCTION}\n\nOtázka používateľa: {user_message}"
        
        response = chat_session.send_message(full_prompt)
        
        return jsonify({
            "response": response.text,
            "status": "success"
        })

    except Exception as e:
        print(f"Chyba: {e}")
        return jsonify({"error": "Nastala chyba na strane servera"}), 500

if __name__ == '__main__':
    # Nastavenie pre hostingy ako Render/Heroku
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)