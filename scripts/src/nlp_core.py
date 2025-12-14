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

def is_complex_query(sql_query):
    sql_upper = sql_query.upper()
    
    has_join = 'JOIN' in sql_upper
    has_subquery = sql_upper.count('SELECT') > 1
    has_group_by = 'GROUP BY' in sql_upper
    has_multiple_conditions = sql_upper.count('AND') + sql_upper.count('OR') >= 2
    has_aggregations = any(func in sql_upper for func in ['SUM(', 'COUNT(', 'AVG(', 'MAX(', 'MIN('])
    
    query_length = len(sql_query)
    keyword_count = sum(1 for keyword in ['WHERE', 'JOIN', 'GROUP', 'HAVING', 'ORDER'] if keyword in sql_upper)
    
    complexity_score = sum([
        has_join,
        has_subquery,
        has_group_by and has_aggregations,
        has_multiple_conditions and has_aggregations,
        query_length > 200,
        keyword_count >= 3
    ])
    
    return complexity_score >= 2

def validate_sql_with_llm(user_query, sql_query):
    validation_prompt = f"""Ты эксперт по SQL и анализу требований. Проверь, соответствует ли SQL-запрос исходному заданию.

Исходное задание:
{user_query}

SQL-запрос для проверки:
{sql_query}

Схема базы данных:
- Таблица videos: id (UUID), creator_id (UUID), video_created_at (TIMESTAMP), views_count, likes_count, comments_count, reports_count
- Таблица video_snapshots: id (SERIAL), video_id (UUID), views_count, likes_count, comments_count, reports_count, delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count, created_at (TIMESTAMP)

Проверь:
1. Правильно ли выбраны таблицы (videos или video_snapshots)?
2. Корректно ли применены фильтры (WHERE условия)?
3. Правильно ли используются агрегатные функции (SUM, COUNT и т.д.)?
4. Корректно ли выполнены JOIN'ы, если они нужны?
5. Соответствует ли результат запроса тому, что спрашивается в задании?

Ответь ТОЛЬКО одним словом:
- "VALID" - если SQL запрос полностью соответствует заданию
- "REGENERATE" - если SQL запрос не соответствует заданию и требует перегенерации

Ответ:"""
    
    try:
        response = call_api(validation_prompt, max_tokens=50)
        response_upper = response.strip().upper()
        
        if "VALID" in response_upper:
            return True, "SQL запрос соответствует заданию"
        elif "REGENERATE" in response_upper:
            return False, "SQL запрос не соответствует заданию, требуется перегенерация"
        else:
            return True, "Ответ валидатора неоднозначен, считаем валидным"
    except Exception as e:
        return True, f"Ошибка валидации: {str(e)}, пропускаем проверку"

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
                time.sleep(wait_time)
            else:
                raise ValueError(f"Таймаут запроса после {retries} попыток: {str(e)}")
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
            else:
                raise ValueError(f"Ошибка запроса после {retries} попыток: {str(e)}")
        except Exception as e:
            raise ValueError(f"Неожиданная ошибка при обращении к API: {str(e)}")
    
    if last_error:
        raise ValueError(f"Ошибка при обращении к API: {str(last_error)}")

def generate_sql_from_task(user_query):
    sql_prompt = f"""Дана база данных с двумя таблицами:

Таблица videos:
- id (UUID) - уникальный идентификатор видео
- creator_id (UUID) - идентификатор креатора
- video_created_at (TIMESTAMP) - дата и время публикации видео
- views_count (INTEGER) - итоговое количество просмотров
- likes_count (INTEGER) - итоговое количество лайков
- comments_count (INTEGER) - итоговое количество комментариев
- reports_count (INTEGER) - итоговое количество жалоб

Таблица video_snapshots:
- id (SERIAL) - идентификатор замера
- video_id (UUID) - ссылка на видео (связь с videos.id)
- views_count (INTEGER) - текущее количество просмотров на момент замера
- created_at (TIMESTAMP) - время замера (раз в час)
- delta_views_count (INTEGER) - приращение просмотров с прошлого замера

Правила:
1. UUID пишется в кавычках: 'aca1061a9d324ecf8c3fa2bb32d7be63'.
2. Даты указываются в формате 'YYYY-MM-DD HH:MM:SS'.
3. Числа пишутся без пробелов: 10 000 → 10000.
4. Для анализа итоговой статистики (например, просмотров) используйте таблицу videos.
5. Для анализа изменений за период (например, прироста просмотров) используйте таблицу video_snapshots.
6. Не используйте JOIN, если вся необходимая информация содержится в одной таблице.

Инструкции:
1. Внимательно прочитайте вопрос и определите:
   - Требуемые данные (например, количество, сумма, среднее значение).
   - Условия фильтрации (например, дата, временная последовательность, приращения).
2. Ответ должен содержать только SQL-запрос.
3. Никаких объяснений, комментариев или кода на других языках.

Вопрос:
{user_query}

SQL:
"""
    try:
        sql_response = call_api(sql_prompt, max_tokens=300)
        return sql_response
    except Exception as e:
        raise ValueError(f"Ошибка при обращении к API: {str(e)}")

def process_query(user_query):
    if not API_KEY:
        raise ValueError("API_TOKEN не установлен в переменных окружения")
    
    try:
        max_regenerations = 2
        regeneration_count = 0
        
        while regeneration_count <= max_regenerations:
            sql_response = generate_sql_from_task(user_query)
            
            sql_query = extract_sql_from_response(sql_response, user_query)
            if not sql_query:
                raise ValueError("Нейросеть не смогла сгенерировать валидный SQL-запрос.")
            
            sql_query = fix_numbers_in_sql(sql_query)
            
            is_valid, error_msg = validate_sql_query(sql_query)
            if not is_valid:
                raise ValueError(f"Синтаксическая ошибка в SQL: {error_msg}")
            
            if is_complex_query(sql_query):
                is_sql_valid, _ = validate_sql_with_llm(user_query, sql_query)
                
                if not is_sql_valid and regeneration_count < max_regenerations:
                    regeneration_count += 1
                    continue
            
            return sql_query
        
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg = f"Статус код {e.response.status_code}. Ответ API: {error_detail}"
            except (ValueError, KeyError, TypeError):
                error_msg = f"Статус код {e.response.status_code}. Ответ API: {e.response.text}"
        raise ValueError(f"Ошибка при обращении к API: {error_msg}")
    except Exception as e:
        raise
