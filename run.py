from scripts.src.db_manager import execute_query

# SQL запрос для подсчета суммарного прироста просмотров
# для всех видео креатора в промежутке с 10:00 до 15:00 28 ноября 2025 года
sql_query = """
SELECT creator_id, COUNT(*)
FROM videos
GROUP BY creator_id
HAVING COUNT(*) > 1;
"""

if __name__ == "__main__":
    try:
        result = execute_query(sql_query)
        print(f"{result}")
    except Exception as e:
        print(f"Ошибка: {e}")
