from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app, origins=['*'])

# Твой ключ OpenRouter
OPENROUTER_API_KEY = "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"

# Кэш для законов
laws_cache = {}
CACHE_TIME = 3600  # 1 час

# Словарь с ссылками на все 18 серверов
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

# Список бесплатных моделей
FREE_MODELS = [
    'openrouter/hunter-alpha',      # 1T параметров, 1M контекст
    'openrouter/healer-alpha',      # мультимодальная
    'nvidia/nemotron-3-super',      # 120B параметров
    'meta-llama/llama-3.3-70b',     # Llama 3.3
    'mistralai/mistral-small-3.1',  # Mistral
    'openrouter/free'                # авто-выбор
]

def parse_xenforo_thread(url):
    """Парсит отдельную тему с законом"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        first_post = soup.select_one('.message-main .bbWrapper')
        if first_post:
            return first_post.get_text('\n', strip=True)
    except Exception as e:
        print(f"Error parsing thread {url}: {e}")
    return None

def parse_forum_section(url):
    """Парсит раздел форума, собирает все темы с законами"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    laws = []
    try:
        print(f"Parsing section: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем все темы в разделе
        threads = soup.select('.structItem--thread')
        print(f"Found {len(threads)} threads")
        
        for thread in threads:
            title_elem = thread.select_one('.structItem-title a')
            if title_elem:
                title = title_elem.get_text(strip=True)
                thread_url = urljoin(url, title_elem['href'])
                
                print(f"  Processing: {title}")
                
                # Получаем текст закона из темы
                law_text = parse_xenforo_thread(thread_url)
                
                laws.append({
                    "title": title,
                    "url": thread_url,
                    "text": law_text
                })
                
                time.sleep(1)  # Задержка между запросами
    except Exception as e:
        print(f"Error parsing section {url}: {e}")
    
    return laws

@app.route('/api/laws/<int:server_id>')
def get_laws(server_id):
    """Получает законы конкретного сервера"""
    current_time = time.time()
    
    # Проверяем кэш
    if server_id in laws_cache:
        cache_time, laws = laws_cache[server_id]
        if current_time - cache_time < CACHE_TIME:
            return jsonify({
                "server_id": server_id,
                "laws": laws,
                "cached": True
            })
    
    if server_id not in SERVERS:
        return jsonify({"error": "Server not found"}), 404
    
    server = SERVERS[server_id]
    all_laws = []
    
    # Если несколько ссылок (как у Детройта)
    if 'urls' in server:
        for url in server['urls']:
            section_laws = parse_forum_section(url)
            all_laws.extend(section_laws)
    else:
        all_laws = parse_forum_section(server['url'])
    
    # Сохраняем в кэш
    laws_cache[server_id] = (current_time, all_laws)
    
    return jsonify({
        "server_id": server_id,
        "server_name": server['name'],
        "laws": all_laws,
        "cached": False
    })

@app.route('/api/ask', methods=['POST'])
def ask_ai():
    """Отправляет вопрос в OpenRouter с бесплатными моделями"""
    try:
        data = request.json
        question = data.get('question', '')
        server_id = data.get('server_id')
        server_laws = data.get('laws', [])
        
        # Формируем промпт с законами сервера
        laws_text = ""
        for law in server_laws[:10]:
            if law.get('text'):
                laws_text += f"\n📌 {law['title']}:\n{law['text'][:500]}...\n"
        
        server_name = SERVERS.get(server_id, {}).get('name', f'Server {server_id}')
        
        prompt = f"""Ты - юридический помощник для RP сервера {server_name} (ID: {server_id}). 
Отвечай на русском языке строго по следующей структуре:

📌 1. КРАТКИЙ ИТОГ:
[Один четкий ответ: можно ли это делать или нет]

---

⚖️ 2. АНАЛИЗ ЗАКОНОДАТЕЛЬСТВА:
[Анализ на основе предоставленных законов]

---

💡 3. ЮРИДИЧЕСКАЯ КОНСУЛЬТАЦИЯ:
[Развернутое объяснение]

---

🚀 4. РЕКОМЕНДАЦИИ:
[Что делать в данной ситуации]

Законы сервера для анализа:
{laws_text}

Вопрос пользователя: {question}"""

        # Пробуем модели по очереди
        for model in FREE_MODELS:
            try:
                response = requests.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://top4ik202118-cloud.github.io/alegrobas-bot/',
                        'X-Title': 'Alegrobas Bot'
                    },
                    json={
                        'model': model,
                        'messages': [
                            {'role': 'system', 'content': 'Ты юридический помощник для RP серверов.'},
                            {'role': 'user', 'content': prompt}
                        ],
                        'temperature': 0.3,
                        'max_tokens': 2000
                    },
                    timeout=15
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result['choices'][0]['message']['content']
                    return jsonify({'answer': answer})
                    
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue
        
        # Если все модели упали
        return jsonify({'answer': '⚠️ ИИ временно недоступен. Попробуйте позже или используйте раздел "Законка".'})
        
    except Exception as e:
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
