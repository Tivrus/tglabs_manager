import re
import os
import time
import requests
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

API_KEY = os.getenv("API_TOKEN", "")
API_URL = "https://api.publicai.co/v1/chat/completions"
MODEL_NAME = os.getenv("PUBLICAI_MODEL_NAME", "swiss-ai/apertus-8b-instruct")

def fix_numbers_in_sql(sql_query):
    def fix_number(match):
        operator = match.group(1)
        number_str = match.group(2)
        fixed_number = number_str.replace(' ', '')
        return f'{operator} {fixed_number}'
    
    pattern = r'([<>=!]+)\s+(\d+(?:\s+\d+)+)(?=\s|;|\)|$|AND|OR)'
    sql_query = re.sub(pattern, fix_number, sql_query, flags=re.IGNORECASE)
    return sql_query

def validate_sql_query(sql_query):
    if not sql_query:
        return False, "SQL-запрос пустой"
    
    single_quotes = sql_query.count("'")
    double_quotes = sql_query.count('"')
    open_parens = sql_query.count('(')
    close_parens = sql_query.count(')')
    
    if single_quotes % 2 != 0:
        return False, f"Незакрытые одинарные кавычки (найдено {single_quotes} кавычек)"
    if double_quotes % 2 != 0:
        return False, f"Незакрытые двойные кавычки (найдено {double_quotes} кавычек)"
    if open_parens != close_parens:
        return False, f"Незакрытые скобки (открывающих: {open_parens}, закрывающих: {close_parens})"
    
    return True, "OK"

def extract_sql_from_response(response_text, user_query=None):
    uuid_pattern = r'([a-f0-9]{32})'
    user_uuids = re.findall(uuid_pattern, user_query or "", re.IGNORECASE)
    
    text_after_sql = response_text.split("SQL:")[-1].strip()
    text_after_sql = re.sub(r'```sql\s*', '', text_after_sql, flags=re.IGNORECASE)
    text_after_sql = re.sub(r'```\s*', '', text_after_sql)
    
    sql_keywords = ["SELECT", "WITH"]
    for keyword in sql_keywords:
        idx = text_after_sql.upper().find(keyword)
        if idx != -1 and (idx == 0 or not text_after_sql[idx-1].isalnum()):
            sql = text_after_sql[idx:].strip()
            if ";" in sql:
                sql = sql[:sql.index(";") + 1].strip()
            else:
                sql += ";"
            
            if user_uuids:
                sql_uuids = re.findall(uuid_pattern, sql, re.IGNORECASE)
                if sql_uuids and any(uuid.lower() in [s.lower() for s in sql_uuids] for uuid in user_uuids):
                    return sql
            return sql
    
    return None

def call_api(prompt, max_tokens=300, retries=3):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "TGLabsManager/1.0"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1
    }
    
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(
                API_URL, 
                json=payload, 
                headers=headers, 
                timeout=(10, 60)
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("choices") and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise ValueError("Пустой ответ от API")
                
        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"Таймаут запроса (попытка {attempt + 1}/{retries}). Повтор через {wait_time} сек...")
                time.sleep(wait_time)
            else:
                raise ValueError(f"Таймаут запроса после {retries} попыток: {str(e)}")
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"Ошибка запроса (попытка {attempt + 1}/{retries}): {str(e)}. Повтор через {wait_time} сек...")
                time.sleep(wait_time)
            else:
                raise ValueError(f"Ошибка запроса после {retries} попыток: {str(e)}")
        except Exception as e:
            raise ValueError(f"Неожиданная ошибка при обращении к API: {str(e)}")
    
    if last_error:
        raise ValueError(f"Ошибка при обращении к API: {str(last_error)}")

def formulate_task(user_query):
    task_prompt = f"""
Дана база данных с двумя таблицами:

Таблица videos:
- id (UUID) - уникальный идентификатор видео
- creator_id (UUID) - идентификатор креатора (владельца видео)
- video_created_at (TIMESTAMP) - дата и время публикации видео
- views_count (INTEGER) - итоговое количество просмотров

Таблица video_snapshots:
- id (SERIAL) - идентификатор замера
- video_id (UUID) - ссылка на видео (связь с videos.id через внешний ключ)
- views_count (INTEGER) - текущее количество просмотров на момент замера
- created_at (TIMESTAMP) - время замера (раз в час)
- delta_views_count (INTEGER) - приращение просмотров с прошлого замера

ВАЖНО о связях:
- video_snapshots.video_id связан с videos.id (это ID видео, а не креатора!)
- Чтобы найти видео конкретного креатора, нужно фильтровать по videos.creator_id
- Если вопрос про креатора и нужны данные из video_snapshots, ОБЯЗАТЕЛЬНО нужен JOIN:
  video_snapshots JOIN videos ON video_snapshots.video_id = videos.id
  И фильтровать по videos.creator_id

Задача: Проанализируй вопрос пользователя и сформулируй детальное техническое задание для генерации SQL-запроса.

Вопрос пользователя:
{user_query}

Сформулируй детальное техническое задание, которое должно включать:
1. Какую таблицу(ы) нужно использовать (videos или video_snapshots или обе)
2. Если нужны данные по креатору из video_snapshots - ОБЯЗАТЕЛЬНО указать необходимость JOIN с videos
3. Какие поля нужны для ответа (указать полное имя таблицы.поле)
4. Какие условия фильтрации применять:
   - Если фильтр по креатору: videos.creator_id = 'UUID'
   - Если фильтр по дате/времени: указать поле (created_at или video_created_at) и интервал
5. Какие агрегатные функции использовать (COUNT, SUM, AVG и т.д.) и над какими полями
6. Особые требования (например, суммирование изменений между замерами)

Ответ должен быть структурированным и конкретным, без SQL-кода, только описание задачи.
ВСЕГДА указывай полные имена таблиц и полей (например, videos.creator_id, video_snapshots.delta_views_count).

Техническое задание:
"""
    try:
        task_description = call_api(task_prompt, max_tokens=400)
        print(f"Техническое задание от первой нейросети:\n{task_description}")
        print("-" * 80)
        return task_description
    except Exception as e:
        print(f"Ошибка при формулировании задачи: {str(e)}")
        raise ValueError(f"Ошибка при обращении к API: {str(e)}")

def generate_sql_from_task(user_query, task_description):
    sql_prompt = f"""
Дана база данных с двумя таблицами:

Таблица videos:
- id (UUID) - уникальный идентификатор видео
- creator_id (UUID) - идентификатор креатора (владельца видео)
- video_created_at (TIMESTAMP) - дата и время публикации видео
- views_count (INTEGER) - итоговое количество просмотров

Таблица video_snapshots:
- id (SERIAL) - идентификатор замера
- video_id (UUID) - ссылка на видео (связь с videos.id через внешний ключ)
- views_count (INTEGER) - текущее количество просмотров на момент замера
- created_at (TIMESTAMP) - время замера (раз в час)
- delta_views_count (INTEGER) - приращение просмотров с прошлого замера

КРИТИЧЕСКИ ВАЖНО:
- video_snapshots.video_id - это ID видео, НЕ креатора!
- Если в техническом задании указан фильтр по креатору (creator_id) и используются данные из video_snapshots - ОБЯЗАТЕЛЬНО нужен JOIN:
  FROM video_snapshots 
  JOIN videos ON video_snapshots.video_id = videos.id
  WHERE videos.creator_id = 'UUID_креатора'
- Если в техническом задании указано "JOIN между таблицами" или "фильтр по креатору" - используй JOIN!
- ВСЕГДА используй полные имена таблиц.поле (например, videos.creator_id, video_snapshots.delta_views_count)

Правила:
1. UUID пишется в кавычках: 'aca1061a9d324ecf8c3fa2bb32d7be63'.
2. Даты указываются в формате 'YYYY-MM-DD HH:MM:SS'.
3. Числа пишутся без пробелов: 10 000 → 10000.
4. Строго следуй техническому заданию - если там указан JOIN, используй JOIN!

Исходный вопрос пользователя:
{user_query}

Техническое задание:
{task_description}

Задача: На основе технического задания создай SQL-запрос для PostgreSQL.
ВНИМАТЕЛЬНО прочитай техническое задание и строго следуй ему:
- Если указан JOIN - используй JOIN
- Если указан фильтр по videos.creator_id - используй JOIN с videos и фильтруй по videos.creator_id
- Используй полные имена таблиц.поле как указано в техническом задании

Ответ должен содержать ТОЛЬКО SQL-запрос, без объяснений, комментариев или кода на других языках.

SQL:
"""
    try:
        sql_response = call_api(sql_prompt, max_tokens=300)
        print(f"Ответ второй нейросети: {sql_response}")
        print("-" * 80)
        return sql_response
    except Exception as e:
        print(f"Ошибка при генерации SQL: {str(e)}")
        raise ValueError(f"Ошибка при обращении к API: {str(e)}")

def process_query(user_query):
    print(f"\nВопрос: {user_query}")
    print("-" * 80)
    
    if not API_KEY:
        raise ValueError("API_TOKEN не установлен в переменных окружения")
    
    try:
        print("Шаг 1: Формулирование технического задания...")
        task_description = formulate_task(user_query)
        
        print("Шаг 2: Генерация SQL на основе технического задания...")
        sql_response = generate_sql_from_task(user_query, task_description)
        
        sql_query = extract_sql_from_response(sql_response, user_query)
        if not sql_query:
            print("ОШИБКА: Не удалось извлечь SQL из ответа нейросети")
            print(f"Ответ нейросети: {sql_response}")
            raise ValueError("Нейросеть не смогла сгенерировать валидный SQL-запрос.")
        
        sql_query = fix_numbers_in_sql(sql_query)
        
        is_valid, error_msg = validate_sql_query(sql_query)
        if not is_valid:
            print(f"ОШИБКА валидации SQL: {error_msg}")
            print(f"SQL-запрос: {sql_query}")
            raise ValueError(f"Синтаксическая ошибка в SQL: {error_msg}")
        
        print(f"Финальный SQL: {sql_query}")
        return sql_query
        
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg = f"Статус код {e.response.status_code}. Ответ API: {error_detail}"
            except (ValueError, KeyError, TypeError):
                error_msg = f"Статус код {e.response.status_code}. Ответ API: {e.response.text}"
        print(f"ОШИБКА при запросе к API: {error_msg}")
        raise ValueError(f"Ошибка при обращении к API: {error_msg}")
    except Exception as e:
        print(f"ОШИБКА при обработке запроса: {str(e)}")
        raise
