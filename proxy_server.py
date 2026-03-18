from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app, origins=['*'])

# ===== GROQ API КЛЮЧ =====
GROQ_API_KEY = "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"

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
                if law_text:
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
    """Отправляет вопрос в Groq с нормальным контекстом"""
    try:
        data = request.json
        question = data.get('question', '')
        server_id = data.get('server_id')
        server_laws = data.get('laws', [])
        
        if not server_laws:
            return jsonify({'answer': '❌ Законы сервера не загружены. Попробуйте позже.'})
        
        # Формируем контекст из законов
        laws_context = ""
        for i, law in enumerate(server_laws[:10]):  # Берем 10 законов
            if law.get('text'):
                laws_context += f"\n=== ЗАКОН {i+1}: {law['title']} ===\n"
                laws_context += law['text'][:1000] + "\n"  # 1000 символов каждого закона
        
        server_name = SERVERS.get(server_id, {}).get('name', f'Сервер {server_id}')
        
        # Промпт, который заставляет Groq ДУМАТЬ
        prompt = f"""Ты — судья в RP сервере {server_name}. Твоя задача — анализировать ситуации и выносить вердикты на основе законов.

Вот законы сервера (только на них и ссылайся):
{laws_context}

Ситуация: {question}

Проанализируй ситуацию шаг за шагом:
1. Что произошло? (кратко перескажи ситуацию)
2. Какие законы из предоставленных могут быть применимы?
3. Почему именно эти законы подходят?
4. Есть ли в законах смягчающие или отягчающие обстоятельства?
5. Какой вердикт?

Теперь дай ответ строго по структуре:

📌 КРАТКИЙ ИТОГ:
[одним предложением: виновен/не виновен, есть нарушение/нет]

⚖️ ПРИМЕНИМЫЕ СТАТЬИ:
• [статья 1] — [цитата из закона]
• [статья 2] — [цитата из закона]

💡 ЮРИДИЧЕСКИЙ АНАЛИЗ:
[подробный разбор ситуации с ссылками на конкретные статьи]

🚀 РЕКОМЕНДАЦИЯ:
[что делать дальше: штраф, арест, предупреждение, вызвать прокурора и т.д.]"""

        # Отправляем в Groq
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {'role': 'system', 'content': 'Ты судья в RP проекте. Твои ответы должны быть основаны только на предоставленных законах. Анализируй ситуацию глубоко, не ограничивайся простым поиском слов.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,  # Немного творчества для анализа
                'max_tokens': 3000
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            return jsonify({'answer': answer})
        else:
            print(f"Groq error: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Если Groq не сработал, пробуем запасной вариант
            fallback_prompt = f"""Законы сервера {server_name} (кратко):
{laws_context[:2000]}

Вопрос: {question}

Ответь кратко: есть нарушение или нет? Если да, то по какой статье?"""
            
            response2 = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama-3.1-8b-instant',  # Более быстрая модель
                    'messages': [{'role': 'user', 'content': fallback_prompt}],
                    'temperature': 0.1,
                    'max_tokens': 1000
                },
                timeout=30
            )
            
            if response2.status_code == 200:
                result2 = response2.json()
                answer2 = result2['choices'][0]['message']['content']
                return jsonify({'answer': answer2})
            else:
                return jsonify({'error': f'Groq API error: {response.status_code}'}), 500
                
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
