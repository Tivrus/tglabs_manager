import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def connect_to_db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

def execute_query(sql_query):
    conn = None
    cursor = None
    try:
        conn = connect_to_db()
        cursor = conn.cursor()

        sql_upper = sql_query.strip().upper()
        if not sql_upper.startswith('SELECT'):
            raise ValueError("Разрешены только SELECT запросы")

        cursor.execute(sql_query)
        result = cursor.fetchone()
        
        if result is None:
            return 0
        
        value = result[0] if isinstance(result, tuple) else result
        
        if value is None:
            return 0
        
        return value
        
    except psycopg2.Error as e:
        raise ValueError(f"Ошибка выполнения SQL-запроса: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()