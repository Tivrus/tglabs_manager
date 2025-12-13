from transformers import AutoModelForImageTextToText, AutoTokenizer
import torch
import os
import re
import glob
from modelscope import snapshot_download

device = "cuda" if torch.cuda.is_available() else "cpu"

model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../npl_model"))
model_name = "Qwen/Qwen2.5-VL-3B-Instruct"

def check_model_exists(model_path):
    safetensors_files = glob.glob(os.path.join(model_path, "*.safetensors"))
    config_exists = os.path.exists(os.path.join(model_path, "config.json"))
    return len(safetensors_files) > 0 and config_exists

def download_model_with_modelscope(model_name, target_path):
    print("Модель не найдена. Начинаю установку через ModelScope...")
    print(f"Модель: {model_name}")
    print(f"Путь сохранения: {target_path}")
    
    os.makedirs(target_path, exist_ok=True)
    
    try:
        downloaded_path = snapshot_download(
            model_id=model_name,
            cache_dir=target_path,
            local_dir=target_path,
            local_files_only=False
        )
        print(f"Модель успешно установлена в: {downloaded_path}")
        return True
    except Exception as e:
        print(f"Ошибка при установке модели: {str(e)}")
        raise

if not check_model_exists(model_path):
    download_model_with_modelscope(model_name, model_path)

load_path = model_path
print("Загрузка токенизатора...")
tokenizer = AutoTokenizer.from_pretrained(load_path, trust_remote_code=True)

print("Загрузка модели...")
model = AutoModelForImageTextToText.from_pretrained(
    load_path,
    dtype=torch.float16 if device == "cuda" else torch.float32,
    trust_remote_code=True
).to(device)
print("Модель успешно загружена")

def extract_sql_from_response(response_text):
    if not response_text or not isinstance(response_text, str):
        return None
    
    # Удаляем префиксы перед SQL
    if "SQL-запрос:" in response_text:
        response_text = response_text.split("SQL-запрос:")[-1]
    if "SQL:" in response_text:
        response_text = response_text.split("SQL:")[-1]
    
    # Паттерны для извлечения SQL из markdown блоков
    sql_patterns = [
        r"```sql\s*(.*?)\s*```",
        r"```\s*(SELECT.*?)\s*```",
        r"```\s*(.*?)\s*```",
    ]
    
    for pattern in sql_patterns:
        match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1)
            if sql:
                sql = sql.strip()
                if sql and sql.upper().startswith(('SELECT', 'WITH')):
                    return sql
    
    # Поиск SQL по ключевым словам
    sql_keywords = ["SELECT", "WITH"]
    for keyword in sql_keywords:
        idx = response_text.upper().find(keyword)
        if idx != -1:
            sql = response_text[idx:].strip()
            if sql:
                # Извлекаем SQL до точки с запятой или до конца строки
                if ";" in sql:
                    sql = sql[:sql.index(";") + 1]
                else:
                    # Берем первую строку, если нет точки с запятой
                    first_line = sql.split('\n')[0].strip()
                    if first_line:
                        sql = first_line + ";"
                    else:
                        continue
                if sql.upper().startswith(('SELECT', 'WITH')):
                    return sql
    
    return None

def process_query(user_query):
    prompt = f"""Ты — SQL-эксперт. Преобразуй вопрос пользователя в SQL-запрос для PostgreSQL.

СХЕМА БАЗЫ ДАННЫХ:

Таблица videos (итоговая статистика по видео):
- id (UUID) — идентификатор видео
- creator_id (UUID) — идентификатор креатора
- video_created_at (timestamp) — дата и время публикации видео
- views_count (integer) — финальное количество просмотров
- likes_count (integer) — финальное количество лайков
- comments_count (integer) — финальное количество комментариев
- reports_count (integer) — финальное количество жалоб
- created_at (timestamp) — служебное поле
- updated_at (timestamp) — служебное поле

Таблица video_snapshots (почасовые замеры по видео):
- id (integer) — идентификатор снапшота
- video_id (UUID) — ссылка на видео (связь с videos.id)
- views_count (integer) — текущее количество просмотров на момент замера
- likes_count (integer) — текущее количество лайков на момент замера
- comments_count (integer) — текущее количество комментариев на момент замера
- reports_count (integer) — текущее количество жалоб на момент замера
- delta_views_count (integer) — приращение просмотров с прошлого замера
- delta_likes_count (integer) — приращение лайков с прошлого замера
- delta_comments_count (integer) — приращение комментариев с прошлого замера
- delta_reports_count (integer) — приращение жалоб с прошлого замера
- created_at (timestamp) — время замера (раз в час)
- updated_at (timestamp) — служебное поле

ВАЖНО:
- Для подсчета общего количества видео используй: SELECT COUNT(*) FROM videos;
- Для подсчета просмотров/лайков/комментариев используй SUM() из таблицы videos
- Для подсчета прироста используй SUM(delta_*) из таблицы video_snapshots
- Для фильтрации по дате используй created_at в video_snapshots или video_created_at в videos
- Даты в формате: 'YYYY-MM-DD' или можно использовать DATE(created_at) = 'YYYY-MM-DD'
- Для диапазона дат используй: created_at >= 'YYYY-MM-DD' AND created_at <= 'YYYY-MM-DD'
- Для фильтрации по конкретной дате используй: DATE(created_at) = 'YYYY-MM-DD'
- UUID значения должны быть в одинарных кавычках: 'aca1061a9d324ecf8c3fa2bb32d7be63'

ПАРСИНГ РУССКИХ ДАТ:
- "28 ноября 2025" → '2025-11-28'
- "1 ноября 2025" → '2025-11-01'
- "с 1 по 5 ноября 2025" → video_created_at >= '2025-11-01' AND video_created_at <= '2025-11-05 23:59:59'
- "с 1 ноября 2025 по 5 ноября 2025 включительно" → video_created_at >= '2025-11-01' AND video_created_at <= '2025-11-05 23:59:59'
- Месяцы: январь=01, февраль=02, март=03, апрель=04, май=05, июнь=06, июль=07, август=08, сентябрь=09, октябрь=10, ноябрь=11, декабрь=12

ПРИМЕРЫ:
Вопрос: "Сколько всего видео есть в системе?"
SQL: SELECT COUNT(*) FROM videos;

Вопрос: "Сколько видео набрало больше 100000 просмотров за всё время?"
SQL: SELECT COUNT(*) FROM videos WHERE views_count > 100000;

Вопрос: "На сколько просмотров в сумме выросли все видео 28 ноября 2025?"
SQL: SELECT COALESCE(SUM(delta_views_count), 0) FROM video_snapshots WHERE DATE(created_at) = '2025-11-28';

Вопрос: "Сколько разных видео получали новые просмотры 27 ноября 2025?"
SQL: SELECT COUNT(DISTINCT video_id) FROM video_snapshots WHERE DATE(created_at) = '2025-11-27' AND delta_views_count > 0;

Вопрос: "Сколько видео у креатора с id aca1061a9d324ecf8c3fa2bb32d7be63 вышло с 1 ноября 2025 по 5 ноября 2025 включительно?"
SQL: SELECT COUNT(*) FROM videos WHERE creator_id = 'aca1061a9d324ecf8c3fa2bb32d7be63' AND video_created_at >= '2025-11-01' AND video_created_at <= '2025-11-05 23:59:59';

Вопрос: "Сколько видео у креатора с id aca1061a9d324ecf8c3fa2bb32d7be63 набрали больше 10000 просмотров по итоговой статистике?"
SQL: SELECT COUNT(*) FROM videos WHERE creator_id = 'aca1061a9d324ecf8c3fa2bb32d7be63' AND views_count > 10000;

Вопрос: {user_query}
SQL:"""

    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,  # Уменьшено с 200 до 100 - SQL запросы обычно короче
            do_sample=False,  # Жадный поиск быстрее, чем сэмплирование
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            num_beams=1,  # Отключение beam search для ускорения (greedy decoding)
            early_stopping=True,  # Остановка при достижении EOS токена
            use_cache=True  # Использование кэша для ускорения
        )

    full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    sql_query = extract_sql_from_response(full_response)
    
    if sql_query is None:
        raise ValueError(
            f"Нейросеть не смогла сгенерировать валидный SQL-запрос.\n"
            f"Ответ модели: {full_response}\n"
            f"С таким промптом нейросеть не смогла вернуть валидные данные на этот вопрос"
        )
    
    sql_query = sql_query.strip()
    if not sql_query.endswith(';'):
        sql_query += ';'
    
    return sql_query
