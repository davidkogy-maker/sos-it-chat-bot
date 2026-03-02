import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, template_folder='templates')
CORS(app)

# Konfigurácia API
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"
genai.configure(api_key=API_KEY)

# AKTUALIZÁCIA: Skúsime univerzálny alias modelu bez problematických nástrojov
# Vymazal som sekciu 'tools', aby aplikácia nepadala na neznámych poliach
model = genai.GenerativeModel(model_name='gemini-1.5-flash')

SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre SOŠ IT Ostrovského 1, Košice. 
Tvojou úlohou je poskytovať presné informácie o škole.

ODBORY: Inteligentné technológie, Siete, Programovanie, Grafik, Správca.
MATURITY 2026: SJL je 10.3.2026. JARNÉ PRÁZDNINY: 2.3.-6.3.2026.
NOTEBOOKY: Vyžaduje sa dedikovaná GPU (OpenGL 4.3).
MIESTNOSŤ PSYCHOLÓGA: 022.
Web: https://ostrov.edupage.org/
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
            return jsonify({"response": "Neprijal som žiadnu správu."})

        # Generovanie odpovede
        prompt = f"{SYSTEM_INSTRUCTION}\n\nPoužívateľ: {user_message}"
        response = model.generate_content(prompt)
        
        if response and response.text:
            return jsonify({"response": response.text})
        else:
            return jsonify({"response": "Prepáč, momentálne neviem odpovedať."})
    
    except Exception as e:
        print(f"DEBUG: {e}")
        return jsonify({"response": f"Chyba: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
