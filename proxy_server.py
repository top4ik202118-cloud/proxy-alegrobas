from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app)  # Разрешаем запросы с любого домена

# Кэш для законов (чтобы не долбить форум каждый раз)
laws_cache = {}
CACHE_TIME = 3600  # 1 час

# Словарь с ссылками на все 18 серверов
SERVERS = {
    1: {
        "name": "New York", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.84/"
    },
    2: {
        "name": "Detroit", 
        "urls": [
            "https://forum.majestic-rp.ru/forums/kodeksy.353/",
            "https://forum.majestic-rp.ru/forums/zakony.354/"
        ]
    },
    3: {
        "name": "Chicago", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.255/"
    },
    4: {
        "name": "San Francisco", 
        "url": "https://forum.majestic-rp.ru/forums/odobrennyye-zakonoproyekty.344/"
    },
    5: {
        "name": "Atlanta", 
        "url": "https://forum.majestic-rp.ru/forums/odobrennyye-zakonoproyekty.562/"
    },
    6: {
        "name": "San Diego", 
        "url": "https://forum.majestic-rp.ru/forums/normativno-pravovyye-akty.580/"
    },
    7: {
        "name": "Los Angeles", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.693/"
    },
    8: {
        "name": "Miami", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.773/"
    },
    9: {
        "name": "Las Vegas", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.820/"
    },
    10: {
        "name": "Washington", 
        "url": "https://forum.majestic-rp.ru/forums/odobrennyye-zakonoproyekty.895/"
    },
    11: {
        "name": "Dallas", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.954/"
    },
    12: {
        "name": "Boston", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1017/"
    },
    13: {
        "name": "Houston", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1104/"
    },
    14: {
        "name": "Seattle", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1163/"
    },
    15: {
        "name": "Phoenix", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1213/"
    },
    16: {
        "name": "Denver", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1276/"
    },
    17: {
        "name": "Portland", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1338/"
    },
    18: {
        "name": "Orlando", 
        "url": "https://forum.majestic-rp.ru/forums/zakonodatel-naya-baza.1405/"
    }
}

def parse_xenforo_thread(url):
    """Парсит отдельную тему с законом"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем первый пост в теме (там текст закона)
        first_post = soup.select_one('.message-main .bbWrapper')
        if first_post:
            return first_post.get_text('\n', strip=True)
    except Exception as e:
        print(f"Error parsing thread {url}: {e}")
    return None

def parse_forum_section(url):
    """Парсит раздел форума, собирает все темы с законами"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
                    "text": law_text,
                    "category": detect_category(title)
                })
                
                time.sleep(1)  # Задержка между запросами
    except Exception as e:
        print(f"Error parsing section {url}: {e}")
    
    return laws

def detect_category(title):
    """Определяет категорию закона по названию"""
    title_lower = title.lower()
    if 'уголовн' in title_lower:
        return 'criminal'
    elif 'административн' in title_lower:
        return 'admin'
    elif 'дорожн' in title_lower or 'пдд' in title_lower:
        return 'road'
    elif 'задержан' in title_lower:
        return 'detention'
    else:
        return 'other'

@app.route('/api/laws/<int:server_id>')
def get_laws(server_id):
    """Получает законы конкретного сервера"""
    # Проверяем кэш
    current_time = time.time()
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

@app.route('/api/servers')
def list_servers():
    """Возвращает список всех серверов"""
    servers_list = []
    for server_id, server_data in SERVERS.items():
        servers_list.append({
            "id": server_id,
            "name": server_data["name"]
        })
    return jsonify(servers_list)

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Анализирует вопрос пользователя"""
    data = request.json
    question = data.get('question', '')
    server_id = data.get('server_id')
    
    if not server_id:
        return jsonify({"error": "Server ID required"}), 400
    
    # Получаем законы сервера
    if server_id not in laws_cache:
        # Если нет в кэше - парсим
        server = SERVERS.get(server_id)
        if not server:
            return jsonify({"error": "Server not found"}), 404
        
        all_laws = []
        if 'urls' in server:
            for url in server['urls']:
                all_laws.extend(parse_forum_section(url))
        else:
            all_laws = parse_forum_section(server['url'])
        
        laws_cache[server_id] = (time.time(), all_laws)
        laws_data = all_laws
    else:
        _, laws_data = laws_cache[server_id]
    
    # Здесь будет логика анализа (пока заглушка)
    # В будущем подключим DeepSeek API для реального анализа
    
    return jsonify({
        "question": question,
        "server_id": server_id,
        "analysis": "Анализ в разработке",
        "laws_used": len(laws_data)
    })

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "servers": len(SERVERS)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
