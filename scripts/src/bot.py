import telebot
from nlp_core import process_query
from db_manager import execute_query
from dotenv import load_dotenv
import os

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
if not os.path.exists(env_path):
    raise FileNotFoundError(f"Файл .env не найден по пути: {env_path}\nСоздайте файл .env с переменными окружения.(см. README.md)")

load_dotenv(env_path)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в файле .env")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
Привет! Я бот для анализа данных о видео.

Задайте вопрос на русском языке, и я верну результат в виде числа.

Примеры вопросов:
• Сколько всего видео есть в системе?
• Сколько видео набрало больше 100000 просмотров?
• На сколько просмотров в сумме выросли все видео 28 ноября 2025?
• Сколько разных видео получали новые просмотры 27 ноября 2025?
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_query = message.text.strip()
    
    if not user_query:
        bot.reply_to(message, "Пожалуйста, задайте вопрос.")
        return
    
    # processing_msg = None
    try:
        # processing_msg = bot.reply_to(message, "Обрабатываю запрос...")
        sql_query = process_query(user_query)
        result = execute_query(sql_query)
        # if processing_msg:
        #     try:
        #         bot.delete_message(message.chat.id, processing_msg.message_id)
        #     except Exception:
        #         pass
        
        bot.reply_to(message, str(result))
        
    except ValueError as e:
        print(e)
        # if processing_msg:
        #     try:
        #         bot.delete_message(message.chat.id, processing_msg.message_id)
        #     except Exception:
        #         pass
        bot.reply_to(
            message, 
            "Произошла ошибка при обработке запроса.\n"
            "Пожалуйста, попробуйте переформулировать вопрос или обратитесь к администратору."
        )
        
    except Exception as e:
        print(e)
        # if processing_msg:
        #     try:
        #         bot.delete_message(message.chat.id, processing_msg.message_id)
        #     except Exception:
        #         pass
        bot.reply_to(
            message,
            "Произошла внутренняя ошибка.\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору."
        )

if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)