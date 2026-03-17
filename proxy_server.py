from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import json

app = Flask(__name__)
CORS(app)

# OpenRouter API ключ (твой)
OPENROUTER_API_KEY = "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"

# Список серверов
SERVERS = {
    1: "New York", 2: "Detroit", 3: "Chicago", 4: "San Francisco",
    5: "Atlanta", 6: "San Diego", 7: "Los Angeles", 8: "Miami",
    9: "Las Vegas", 10: "Washington", 11: "Dallas", 12: "Boston",
    13: "Houston", 14: "Seattle", 15: "Phoenix", 16: "Denver",
    17: "Portland", 18: "Orlando"
}

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "servers": len(SERVERS)})

@app.route('/api/servers')
def list_servers():
    servers_list = [{"id": sid, "name": name} for sid, name in SERVERS.items()]
    return jsonify(servers_list)

@app.route('/api/ask', methods=['POST'])
def ask_ai():
    try:
        data = request.json
        question = data.get('question', '')
        server_id = data.get('server_id')
        
        server_name = SERVERS.get(server_id, f"Server {server_id}")
        
        prompt = f"Ты юридический помощник для RP сервера {server_name}. Ответь на русском: {question}"
        
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'openrouter/hunter-alpha',
                'messages': [
                    {'role': 'system', 'content': 'Ты помощник для RP сервера. Отвечай кратко и по делу.'},
                    {'role': 'user', 'content': prompt}
                ]
            },
            timeout=30
        )
        
        result = response.json()
        
        if 'choices' in result:
            return jsonify({'answer': result['choices'][0]['message']['content']})
        else:
            return jsonify({'error': 'No response from AI'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
