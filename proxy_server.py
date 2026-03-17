from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app, origins=['*'])

# OpenRouter API ключ (твой)
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
    """Парсит раздел форума"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    laws = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        threads = soup.select('.structItem--thread')
        
        for thread in threads:
            title_elem = thread.select_one('.structItem-title a')
            if title_elem:
                title = title_elem.get_text(strip=True)
                thread_url = urljoin(url, title_elem['href'])
                law_text = parse_xenforo_thread(thread_url)
                laws.append({
                    "title": title,
                    "url": thread_url,
                    "text": law_text
                })
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
    """Отправляет вопрос в OpenRouter с бесплатной моделью"""
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
Отвечай на русском языке строго по следующей структуре. Используй те же заголовки и эмодзи.

📌 1. КРАТКИЙ ИТОГ:
[Один четкий ответ: можно ли это делать или нет, разрешено или запрещено]

---

⚖️ 2. АНАЛИЗ ЗАКОНОДАТЕЛЬСТВА ШТАТА:
Применимые статьи (перечисли все статьи из предоставленных законов, которые относятся к вопросу):

[Название закона], статья [номер]: «[прямая цитата из закона]»
[Название закона], статья [номер]: «[прямая цитата из закона]»

(Добавь все подходящие статьи)

---

💡 3. ЮРИДИЧЕСКАЯ КОНСУЛЬТАЦИЯ:
[Развернутое объяснение на основе статей, почему это так, как применять законы в данной ситуации]

---

🚀 4. РЕКОМЕНДАЦИИ / СЛЕДУЮЩИЕ ШАГИ:
*   [Конкретные действия для сотрудника/гражданина]
*   [Что делать, если]
*   [Как избежать нарушений]

---

🌐 5. СРАВНИТЕЛЬНО-ПРАВОВОЙ КОММЕНТАРИЙ:
[Сравнение с общей практикой, пояснение логики законов]

Законы сервера для анализа:
{laws_text}

Вопрос пользователя: {question}

Твоя задача - проанализировать ситуацию и ответить строго по указанной структуре.
Используй только информацию из предоставленных законов. Если законов нет - честно скажи, что информации недостаточно."""

        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://top4ik202118-cloud.github.io/alegrobas-bot/',
                'X-Title': 'Alegrobas Bot'
            },
            json={
                'model': 'openrouter/hunter-alpha',
                'messages': [
                    {'role': 'system', 'content': 'Ты юридический помощник для RP серверов. Отвечай строго по структуре с заголовками и эмодзи.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 2000
            },
            timeout=60
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'OpenRouter API returned {response.status_code}'}), 500
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            answer = result['choices'][0]['message']['content']
            return jsonify({'answer': answer})
        else:
            return jsonify({'error': 'No response from AI'}), 500
            
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
