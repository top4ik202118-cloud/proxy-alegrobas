from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app, origins=['*'])

# ===== GEMINI API КЛЮЧ =====
GEMINI_API_KEY = "AIzaSyBpjIz078W8OlF03oapejYOjfHD0oBB3UM"  # Вставь ключ из AI Studio

# ===== КЭШ ДЛЯ ЗАКОНОВ =====
laws_cache = {}
CACHE_TIME = 3600  # 1 час

# ===== СЛОВАРЬ СЕРВЕРОВ =====
SERVERS = {
    1: {"name": "New York", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.84/"},
    2: {"name": "Detroit", "urls": ["https://forum.majestic-rp.ru/forums/kodeksy.353/", "https://forum.majestic-rp.ru/forums/zakony.354/"]},
    3: {"name": "Chicago", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.255/"},
    4: {"name": "San Francisco", "url": "https://forum.majestic-rp.ru/forums/odobrennyye-zakonoproyekty.344/"},
    5: {"name": "Atlanta", "url": "https://forum.majestic-rp.ru/forums/odobrennyye-zakonoproyekty.562/"},
    6: {"name": "San Diego", "url": "https://forum.majestic-rp.ru/forums/normativno-pravovyye-akty.580/"},
    7: {"name": "Los Angeles", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.693/"},
    8: {"name": "Miami", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.773/"},
    9: {"name": "Las Vegas", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.820/"},
    10: {"name": "Washington", "url": "https://forum.majestic-rp.ru/forums/odobrennyye-zakonoproyekty.895/"},
    11: {"name": "Dallas", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.954/"},
    12: {"name": "Boston", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1017/"},
    13: {"name": "Houston", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1104/"},
    14: {"name": "Seattle", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1163/"},
    15: {"name": "Phoenix", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1213/"},
    16: {"name": "Denver", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1276/"},
    17: {"name": "Portland", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1338/"},
    18: {"name": "Orlando", "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1405/"}
}

def parse_xenforo_thread(url):
    """Парсит отдельную тему с законом"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        first_post = soup.select_one('.message-main .bbWrapper')
        if first_post:
            return first_post.get_text('\n', strip=True)
    except Exception as e:
        print(f"Error parsing thread {url}: {e}")
    return None

def parse_forum_section(url):
    """Парсит раздел форума"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    laws = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        threads = soup.select('.structItem--thread')
        
        for thread in threads:
            title_elem = thread.select_one('.structItem-title a')
            if title_elem:
                title = title_elem.get_text(strip=True)
                thread_url = urljoin(url, title_elem['href'])
                law_text = parse_xenforo_thread(thread_url)
                laws.append({"title": title, "url": thread_url, "text": law_text})
                time.sleep(1)
    except Exception as e:
        print(f"Error parsing section {url}: {e}")
    return laws

@app.route('/api/laws/<int:server_id>')
def get_laws(server_id):
    """Получает законы конкретного сервера"""
    current_time = time.time()
    if server_id in laws_cache:
        cache_time, laws = laws_cache[server_id]
        if current_time - cache_time < CACHE_TIME:
            return jsonify({"server_id": server_id, "laws": laws, "cached": True})
    
    if server_id not in SERVERS:
        return jsonify({"error": "Server not found"}), 404
    
    server = SERVERS[server_id]
    all_laws = []
    
    if 'urls' in server:
        for url in server['urls']:
            all_laws.extend(parse_forum_section(url))
    else:
        all_laws = parse_forum_section(server['url'])
    
    laws_cache[server_id] = (current_time, all_laws)
    return jsonify({"server_id": server_id, "server_name": server['name'], "laws": all_laws, "cached": False})

@app.route('/api/ask', methods=['POST'])
def ask_ai():
    """Отправляет вопрос в Gemini"""
    try:
        data = request.json
        question = data.get('question', '')
        server_id = data.get('server_id')
        server_laws = data.get('laws', [])
        
        # Формируем текст законов
        laws_text = ""
        for law in server_laws[:7]:
            if law.get('text'):
                short_text = law['text'][:400] + "..." if len(law['text']) > 400 else law['text']
                laws_text += f"\n📌 {law['title']}:\n{short_text}\n"
        
        server_name = SERVERS.get(server_id, {}).get('name', f'Сервер {server_id}')
        
        # Промпт для Gemini
        prompt = f"""Ты юридический помощник для RP сервера {server_name}.

Законы сервера:
{laws_text}

Вопрос: {question}

Ответь строго по структуре:
📌 1. КРАТКИЙ ИТОГ: [да/нет, можно/нельзя]
⚖️ 2. СТАТЬИ: [какие статьи из законов выше подходят]
💡 3. ОБЪЯСНЕНИЕ: [почему]
🚀 4. РЕКОМЕНДАЦИЯ: [что делать]

Отвечай ТОЛЬКО на основе законов выше. Если в законах нет информации — напиши "❌ В законах нет ответа на этот вопрос"."""

        # Отправляем в Gemini API
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}',
            headers={'Content-Type': 'application/json'},
            json={
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1500
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'answer': answer})
        else:
            print(f"Gemini error: {response.status_code}")
            print(f"Response: {response.text}")
            return jsonify({'error': f'Gemini API returned {response.status_code}'}), 500
                
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers')
def list_servers():
    servers_list = [{"id": sid, "name": s["name"]} for sid, s in SERVERS.items()]
    return jsonify(servers_list)

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "servers": len(SERVERS)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
