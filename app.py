import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__, template_folder='templates')
CORS(app)

# Konfigurácia API
API_KEY = "AIzaSyCfwYxGd5V6AmMw4U58qkfqV-DryQAwFwo"
genai.configure(api_key=API_KEY)

# AKTUALIZÁCIA 2026: Používame Gemini 2.5 Flash
# Výskum potvrdil, že 'models/' prefix netreba, SDK si ho doplní
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[{"google_search": {}}] # ZMENA: staré 'google_search_retrieval' už nefunguje
)

SYSTEM_INSTRUCTION = """
Si oficiálny AI asistent pre SOŠ IT Ostrovského 1, Košice. 
Informuj o odboroch: Inteligentné technológie, Siete, Programovanie, Grafik, Správca.
Maturity 2026: SJL je 10.3.2026. Jarné prázdniny: 2.3.-6.3.2026.
Notebooky: vyžaduje sa dedikovaná GPU (OpenGL 4.3).
Miestnosť psychológa: 022.
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

        # Generovanie s novým modelom
        prompt = f"{SYSTEM_INSTRUCTION}\n\nPoužívateľ: {user_message}"
        response = model.generate_content(prompt)
        
        if response and response.text:
            return jsonify({"response": response.text})
        else:
            return jsonify({"response": "AI v marci 2026 vyžaduje stabilné pripojenie. Skúste znova."})
    
    except Exception as e:
        # Ak by vypísalo chybu o "Paid Services", znamená to, že treba zapnúť Billing v Google Cloud
        print(f"DEBUG: {e}")
        return jsonify({"response": f"Chyba: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
