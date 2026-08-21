from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
import random

from models import init_db, async_session, Answer, Suggestion, Feedback
from facts import get_random_fact, get_fact_by_id, FACTS
from contextlib import asynccontextmanager

from fastapi import Request
from fastapi.responses import JSONResponse
import time
from collections import defaultdict

# Rate limit: 10 запросов за 10 секунд на IP
rate_limit_store = defaultdict(list)
RATE_LIMIT = 10
RATE_WINDOW = 10

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Пропускаем статику
    if request.url.path.startswith("/static"):
        return await call_next(request)

    # Только API
    if request.url.path.startswith("/api/"):
        ip = request.client.host
        now = time.time()

        # Убираем старые запросы
        rate_limit_store[ip] = [t for t in rate_limit_store[ip] if now - t < RATE_WINDOW]

        if len(rate_limit_store[ip]) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"error": "Слишком много запросов. Подождите."}
            )

        rate_limit_store[ip].append(now)

    return await call_next(request)

@app.middleware("http")
async def cache_static_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response

# Подключаем папки со статикой и шаблонами
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Главная страница
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


# Получить случайный вопрос
@app.get("/api/question")
async def get_question():
    fact = get_random_fact()
    # Ищем индекс факта в списке
    fact_id = FACTS.index(fact)  # нужно импортировать FACTS
    return {
        "question": fact["question"],
        "unit": fact["unit"],
        "fact_id": fact_id,
        "image_url": fact.get("image_url", "")
    }


# Проверить ответ
@app.post("/api/check")
async def check_answer(fact_id: int = Body(...), user_answer: float = Body(...)):
    fact = get_fact_by_id(fact_id)
    correct = fact["answer"]

    import math

    # Защита от деления на ноль
    if correct == 0:
        correct = 1
    if user_answer == 0:
        user_answer = 0.01

    ratio = max(user_answer, correct) / min(user_answer, correct)

    if ratio == 1:
        final_score = 15000
        result = "perfect"
        hint = "🔥 Идеально!"
    else:
        log_error = math.log10(ratio)
        points = 15000 * max(0, 1 - log_error / 1.0)
        final_score = max(50, round(points))

        # Определяем результат
        if ratio < 1.5:
            result = "great"
            hint = "👏 Очень близко!"
        elif ratio < 2:
            result = "close"
            hint = "👍 Близко!"
        elif ratio < 5:
            result = "far"
            hint = "🤔 Мимо"
        elif ratio < 10:
            result = "bad"
            hint = "😬 Далеко"
        else:
            result = "miss"
            hint = "💀 Совсем мимо"

    return JSONResponse({
        "result": result,
        "hint": hint,
        "correct_answer": correct,
        "unit": fact["unit"],
        "points": final_score,
        "error_pct": round((ratio - 1) * 100, 1)
    })


# Сохранить ответ игрока
@app.post("/api/save-answer")
async def save_answer(
        fact_id: int = Body(...),
        user_answer: float = Body(...),
        correct_answer: float = Body(...),
        points: int = Body(...),
        user_id: str = Body(...)
):
    async with async_session() as session:
        answer = Answer(
            fact_id=fact_id,
            user_answer=user_answer,
            correct_answer=correct_answer,
            points=points,
            user_id=user_id
        )
        session.add(answer)
        await session.commit()
    return {"status": "ok"}


# Получить статистику по факту
@app.get("/api/stats/{fact_id}")
async def get_stats(fact_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Answer).where(Answer.fact_id == fact_id)
        )
        answers = result.scalars().all()

        if not answers:
            return {
                "bins": [],
                "correct_answer": None,
                "total_answers": 0
            }

        user_answers = [a.user_answer for a in answers]
        correct_answer = answers[0].correct_answer if answers else None
        total = len(user_answers)

        # Всё ещё отдаём старые bins для совместимости,
        # но основное — correct_answer и все ответы
        min_val = min(user_answers)
        max_val = max(user_answers)
        bin_count = 10
        bin_width = (max_val - min_val) / bin_count if max_val > min_val else 1

        bins = []
        for i in range(bin_count):
            bin_start = min_val + i * bin_width
            bin_end = bin_start + bin_width
            count = sum(1 for a in user_answers if bin_start <= a < bin_end)
            if i == bin_count - 1:
                count = sum(1 for a in user_answers if bin_start <= a <= bin_end)
            bins.append(count)

        return {
            "bins": bins,
            "correct_answer": correct_answer,
            "total_answers": total,
            "min_answer": min_val,
            "max_answer": max_val,
            "all_answers": user_answers  # все ответы для гистограммы
        }


def format_label(value):
    if value >= 1000000:
        return f"{value / 1000000:.1f}M"
    elif value >= 1000:
        return f"{value / 1000:.0f}k"
    elif value >= 1:
        return str(int(value))
    elif value >= 0.01:
        return f"{value:.2f}"
    else:
        return f"{value:.4f}"


@app.post("/api/score-percentile")
async def score_percentile(data: dict = Body(...)):
    score = data.get("score", 0)
    async with async_session() as session:
        # Все баллы из всех ответов
        result = await session.execute(select(Answer.points))
        all_points = [row[0] for row in result.all()]

        total = len(all_points)
        if total == 0:
            return {"percentile": 100, "better_than": 0, "total": 0}

        better_than = sum(1 for p in all_points if p <= score)
        percentile = round((better_than / total) * 100)

        return {"percentile": percentile, "better_than": better_than, "total": total}

@app.post("/api/suggest-question")
async def suggest_question(data: dict = Body(...)):
    async with async_session() as session:
        suggestion = Suggestion(
            question=data["question"],
            answer=data["answer"],
            unit=data["unit"],
            email=data.get("email", "")  # ← добавить
        )
        session.add(suggestion)
        await session.commit()
    return {"status": "ok"}

@app.post("/api/feedback")
async def feedback(data: dict = Body(...)):
    async with async_session() as session:
        fb = Feedback(
            text=data["text"],
            email=data.get("email", "")  # ← добавить
        )
        session.add(fb)
        await session.commit()
    return {"status": "ok"}

@app.get("/api/total-answers")
async def total_answers():
    async with async_session() as session:
        result = await session.execute(select(Answer))
        total = len(result.scalars().all())
        return {"total": total}


@app.post("/api/stats-batch")
async def stats_batch(data: dict = Body(...)):
    fact_ids = data.get("fact_ids", [])
    result = {}
    for fact_id in fact_ids:
        async with async_session() as session:
            answers = (await session.execute(
                select(Answer).where(Answer.fact_id == fact_id)
            )).scalars().all()

            if answers:
                user_answers = [a.user_answer for a in answers]
                correct_answer = answers[0].correct_answer
                total = len(user_answers)
                min_val = min(user_answers)
                max_val = max(user_answers)
                bin_count = 10
                bin_width = (max_val - min_val) / bin_count if max_val > min_val else 1
                bins = []
                for i in range(bin_count):
                    start = min_val + i * bin_width
                    end = start + bin_width
                    count = sum(1 for a in user_answers if start <= a < end)
                    if i == bin_count - 1:
                        count = sum(1 for a in user_answers if start <= a <= end)
                    bins.append(count)

                result[str(fact_id)] = {
                    "bins": bins,
                    "correct_answer": correct_answer,
                    "total_answers": total,
                    "min_answer": min_val,
                    "max_answer": max_val,
                    "all_answers": user_answers
                }
            else:
                result[str(fact_id)] = {"bins": [], "total_answers": 0}

    return result