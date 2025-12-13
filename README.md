# RU

### Архитектура
1. **Telegram-бот**
    - Обрабатывает сообщения от пользователей и координирует работу всех модулей.

2. **Модуль генерации SQL**
    - Использует локальную модель ИИ для преобразования вашего текстового запроса в SQL-запрос.

3. **Модуль работы с базой данных**
    - Подключается к PostgreSQL, выполняет SQL-запросы и возвращает результаты.


### Подход к преобразованию текста в SQL
Проект использует **локально развернутую LLM модель** (Qwen2.5-VL-3B-Instruct) для генерации SQL-запросов из естественного языка.


### Описание схемы данных в промпте
Промпт содержит детальное описание структуры базы данных:

1. **Таблица `videos`**: итоговая статистика по видео
    - Поля: id, creator_id, video_created_at, views_count, likes_count, comments_count, reports_count

2. **Таблица `video_snapshots`**: почасовые замеры по видео
    - Поля: video_id, views_count, likes_count, comments_count, reports_count
    - Поля прироста: delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count
    - Связь с таблицей videos через video_id


### Правила преобразования
Промпт включает инструкции по:
- Выбору правильной таблицы для разных типов запросов
- Использованию агрегатных функций (COUNT, SUM)
- Работе с датами и их форматами
- Парсингу русских дат ("28 ноября 2025" → '2025-11-28')
- Форматированию UUID значений


### Примеры в промпте
Промпт содержит несколько примеров вопросов и соответствующих SQL-запросов:


### Извлечение SQL из ответа

После генерации ответа моделью, SQL-запрос извлекается с помощью `re` выражений:
- Поиск SQL в блоках кода (```sql ... ```)
- Поиск SQL-запросов, начинающихся с ключевых слов SELECT или WITH
- Очистка и валидация извлеченного SQL



## Установка и запуск

### Требования
- Python 3.12+
- PostgreSQL 12+
- Локально развернутая модель Qwen2.5-VL-3B-Instruct (В случае её отстутствия она установится автоматически)


#### Шаг 1: Загрузка модели
Модель Qwen2.5-VL-3B-Instruct должна быть размещена в папке `npl_model/` в корне проекта.
Если модель отсутствует, она будет автоматически загружена при первом запуске (требуется интернет-соединение, установка может занять время).

#### Шаг 2: Настройка переменных окружения
Создайте файл `.env` в корне проекта:

```env
# Tg Bot Token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# PostgreSQL DB Configuration
DB_NAME=your_database_name
DB_USER=postgres
DB_PASSWORD= `your_password` 
DB_HOST=localhost
DB_PORT=5432
```


#### Шаг 8: Запуск бота
```bash
cd scripts/src
python bot.py
```
Бот будет запущен и готов к обработке запросов.


### Технологии

- **Python 3.8+** - основной язык программирования
- **PostgreSQL** - база данных
- **pyTelegramBotAPI** - библиотека для работы с Telegram Bot API
- **transformers** - библиотека для работы с LLM моделями
- **PyTorch** - фреймворк для машинного обучения
- **psycopg2** - драйвер PostgreSQL для Python

### Безопасность

- Пользователям не отправляются детали ошибок, только общие сообщения
- Выполняются только SELECT-запросы (валидация в `db_manager.py`)
- Токен бота хранится в переменных окружения, не коммитится в репозиторий



# EN

### Architecture
1. **Telegram Bot**
    - Handles user messages and coordinates the work of all modules.

2. **SQL Generation Module**
    - Uses a local AI model to convert your text query into an SQL query.

3. **Database Module**
    - Connects to PostgreSQL, executes SQL queries, and returns results.


### Approach to Converting Text to SQL
The project uses a **locally deployed LLM model** (Qwen2.5-VL-3B-Instruct) to generate SQL queries from natural language.


### Data Schema Description in Prompt
The prompt contains a detailed description of the database structure:

1. **Table `videos`**: Final statistics for videos
    - Fields: id, creator_id, video_created_at, views_count, likes_count, comments_count, reports_count

2. **Table `video_snapshots`**: Hourly measurements for videos
    - Fields: video_id, views_count, likes_count, comments_count, reports_count
    - Incremental fields: delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count
    - Linked to the `videos` table via `video_id`


### Conversion Rules
The prompt includes instructions on:
- Choosing the correct table for different types of queries
- Using aggregate functions (COUNT, SUM)
- Working with dates and their formats
- Parsing Russian dates ("November 28, 2025" → '2025-11-28')
- Formatting UUID values


### Examples in Prompt
The prompt contains several examples of questions and corresponding SQL queries.


### Extracting SQL from the Response

After generating the response using the model, the SQL query is extracted using `re` expressions:
- Searching for SQL in code blocks (```sql ... ```)
- Searching for SQL queries starting with keywords SELECT or WITH
- Cleaning and validating the extracted SQL



## Installation and Setup

### Requirements
- Python 3.12+
- PostgreSQL 12+
- Locally deployed Qwen2.5-VL-3B-Instruct model (If absent, it will install automatically)


#### Step 1: Downloading the Model
The Qwen2.5-VL-3B-Instruct model should be placed in the `npl_model/` folder in the root directory of the project.
If the model is missing, it will be automatically downloaded during the first run (requires internet connection, installation may take time).

#### Step 2: Setting Up Environment Variables
Create a `.env` file in the root directory of the project:

```env
# Tg Bot Token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# PostgreSQL DB Configuration
DB_NAME=your_database_name
DB_USER=postgres
DB_PASSWORD= `your_password` 
DB_HOST=localhost
DB_PORT=5432
```


#### Step 8: Running the Bot
```bash
cd scripts/src
python bot.py
```
The bot will be launched and ready to process requests.


### Technologies

- **Python 3.8+** - primary programming language
- **PostgreSQL** - database
- **pyTelegramBotAPI** - library for working with Telegram Bot API
- **transformers** - library for working with LLM models
- **PyTorch** - machine learning framework
- **psycopg2** - PostgreSQL driver for Python

### Security

- Users do not receive error details, only general messages
- Only SELECT queries are executed (validation in `db_manager.py`)
- The bot token is stored in environment variables and not committed to the repository