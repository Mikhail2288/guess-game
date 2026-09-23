# Угадай число
https://guessnumber.ru/

Игра на интуицию и чувство масштаба.
## Как играть

1. Вы получаете 5 вопросов о реальных числовых фактах
2. Вводите число — вашу оценку
3. Получаете баллы: чем ближе к истине, тем больше очков
4. После игры видите распределение ответов других игроков

## Стек

### Backend
- Python 3.10
- FastAPI — веб-фреймворк
- SQLAlchemy 2.0 — асинхронный ORM
- asyncpg — драйвер PostgreSQL
- Uvicorn — ASGI-сервер
- Jinja2 — шаблонизатор

### База данных
- PostgreSQL (Neon)
- Таблицы: `answers`, `scores`, `suggestions`, `feedbacks`

### Frontend
- Vanilla JavaScript (без фреймворков)
- Canvas API — отрисовка графиков
- CSS3 — анимации и адаптивная верстка

### Механика начисления баллов

Формула основана на логарифме отношения ответа к правильному:

```python
ratio = max(user_answer, correct) / min(user_answer, correct)
log_error = math.log10(ratio)
points = 15000 * max(0, 1 - log_error / 1.5) ** 0.7
```

## Структура проекта

```
guess-game/
├── main.py              # FastAPI приложение, эндпоинты
├── models.py            # SQLAlchemy модели
├── facts.py             # Загрузка вопросов из CSV
├── facts.csv            # База вопросов (53 штуки)
├── requirements.txt     # Зависимости
├── render.yaml          # Конфиг деплоя
├── templates/
│   └── index.html       # SPA-страница
└── static/
    ├── style.css        # Стили
    ├── favicon.svg      # Иконка
    ├── robots.txt       # Для поисковиков
    ├── privacy.html     # Политика конфиденциальности
    └── images_webp/     # Картинки к вопросам
```



# Станьте частью эксперимента - https://guessnumber.ru/
