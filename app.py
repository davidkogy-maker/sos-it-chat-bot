import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, template_folder='templates')
CORS(app)

# Tvoj API Kľúč
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"
genai.configure(api_key=API_KEY)

# TENTO NÁZOV JE TERAZ SPRÁVNY PRE API v1beta
model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre SOŠ IT Ostrovského 1, Košice. 
Tvojou úlohou je poskytovať presné informácie o škole.

ODBORY: Inteligentné technológie, Informačné a sieťové technológie, Programovanie digitálnych technológií, Správca inteligentných systémov, Grafik digitálnych médií.
NOTEBOOKY: Potrebná dedikovaná grafika (OpenGL 4.3).
TERMÍNY: Jarné prázdniny 2.3.-6.3.2026.
MIESTNOSŤ: Psychológ je v č. 022.
"""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        msg = data.get("message", "").strip()
        if not msg:
            return jsonify({"response": "Prázdna správa."})

        # Jednoduché generovanie bez pýtania sa na zoznam modelov
        response = model.generate_content(f"{SYSTEM_INSTRUCTION}\n\nOtázka: {msg}")
        
        if response and response.text:
            return jsonify({"response": response.text})
        else:
            return jsonify({"response": "AI neodpovedá, skús to neskôr."})
    
    except Exception as e:
        print(f"Chyba: {e}")
        return jsonify({"response": f"Chyba na serveri: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
