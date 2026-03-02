import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, template_folder='templates')
CORS(app)

# Tvoj API Kľúč
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"
genai.configure(api_key=API_KEY)

# OPRAVA: Používame názov modelu, ktorý je 100% podporovaný
model = genai.GenerativeModel('gemini-pro') 

SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre SOŠ IT Ostrovského 1, Košice. 
Tvojou úlohou je poskytovať presné a užitočné informácie o škole.

KONTAKTNÉ ÚDAJE:
- Adresa: Ostrovského 1, 040 01 Košice.
- Email: skola@ostrovskeho.sk, Telefón: +421 55 643 68 91.
- Riaditeľka: Ing. Elena Tibenská.

PODROBNÉ ODBORY (2026/2027):
1. 2559 M Inteligentné technológie: Zameranie na AI, IoT, robotiku a kyberbezpečnosť.
2. 2561 M Informačné a sieťové technológie: Hardvér, správa sietí, programovanie v Jave.
3. 2573 M Programovanie digitálnych technológií: Vývoj hier, mobilné aplikácie, VR/AR.
4. 2571 K Správca inteligentných a digitálnych systémov: Praktický odbor, servis, senzory.
5. 3447 K Grafik digitálnych médií: Práca s Adobe balíkom, digitálna fotografia a weby.

ŠPECIFICKÉ INFORMÁCIE Z MANUÁLU:
- Notebooky: Každý žiak potrebuje vlastný notebook s Windows 10/11. Kľúčová je dedikovaná grafická karta (GPU) s podporou OpenGL 4.3 a vyššou.
- Termíny 2026: Jarné prázdniny pre Košický kraj sú od 2.3. do 6.3.2026. Maturita zo SJL je 10.3.2026.
- Psychológ: Školský psychológ sa nachádza v miestnosti č. 022.
- Internát a strava: Škola má vlastný školský internát a jedáleň priamo v areáli.

KOMUNIKAČNÉ PRAVIDLÁ:
- Odpovedaj profesionálne, ale priateľsky.
- Ak nepoznáš konkrétnu odpoveď, napíš "Túto informáciu nemám špecifikovanú v manuáli" a pridaj odkaz na https://ostrov.edupage.org/.
- Dodržuj prísne GDPR.
"""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "")
        
        if not user_message:
            return jsonify({"response": "Neprijal som žiadnu správu."})

        # OPRAVA: Jednoduchšie volanie modelu pre lepšiu kompatibilitu
        prompt = f"{SYSTEM_INSTRUCTION}\n\nPoužívateľ: {user_message}"
        response = model.generate_content(prompt)
        
        if response and response.text:
            return jsonify({"response": response.text})
        else:
            return jsonify({"response": "Prepáč, Gemini vygeneroval prázdnu odpoveď."})
    
    except Exception as e:
        print(f"Chyba: {e}")
        return jsonify({"response": f"Chyba na serveri: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
