import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, template_folder='templates')
CORS(app)

# Konfigurácia API
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"
genai.configure(api_key=API_KEY)

# Dynamický výber modelu (nájde prvý funkčný model v tvojom regióne)
def get_model():
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            return genai.GenerativeModel(m.name)
    return genai.GenerativeModel('gemini-1.5-flash') # Záloha

model = get_model()

SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre SOŠ IT Ostrovského 1, Košice. 
Tvojou úlohou je poskytovať presné a užitočné informácie o škole.

KONTAKTNÉ ÚDAJE:
- Adresa: Ostrovského 1, 040 01 Košice.
- Email: skola@ostrovskeho.sk, Telefón: +421 55 643 68 91.
- Riaditeľka: Ing. Elena Tibenská.

PODROBNÉ ODBORY (2026/2027):
1. 2559 M Inteligentné technológie: AI, IoT, robotika, kyberbezpečnosť.
2. 2561 M Informačné a sieťové technológie: Siete, hardvér, Java.
3. 2573 M Programovanie digitálnych technológií: Vývoj hier, VR/AR, mobilné aplikácie.
4. 2571 K Správca inteligentných a digitálnych systémov: Praktický odbor, senzory, servis.
5. 3447 K Grafik digitálnych médií: Adobe balík, weby, fotografia.

DÔLEŽITÉ DETAILY:
- Notebooky: Potrebná dedikovaná GPU (OpenGL 4.3 a vyššie).
- Termíny: Jarné prázdniny (Košice) sú 2.3.-6.3.2026. Maturita SJL 10.3.2026.
- Miestnosti: Psychológ je v miestnosti č. 022.
- Odkazuj na: https://ostrov.edupage.org/
"""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return jsonify({"response": "Neprijal som správu."})

        # Generovanie odpovede s tvojím manuálom
        prompt = f"{SYSTEM_INSTRUCTION}\n\nPoužívateľ sa pýta: {user_message}"
        response = model.generate_content(prompt)
        
        if response and response.text:
            return jsonify({"response": response.text})
        else:
            return jsonify({"response": "AI momentálne neodpovedá, skúste to o chvíľu."})
    
    except Exception as e:
        print(f"DEBUG CHYBA: {e}")
        return jsonify({"response": f"Chyba: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

