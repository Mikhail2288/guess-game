from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
import random

from models import init_db, async_session, Score, Answer, Suggestion, Feedback
from facts import get_random_fact, get_fact_by_id, FACTS
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

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
    error_pct = abs(user_answer - correct) / correct * 100

    MAX_SCORE = 15000
    MIN_SCORE = 100

    # Плавная формула: чем меньше ошибка, тем больше баллов
    # error_pct = 0 → 15000
    # error_pct = 5 → 12000
    # error_pct = 10 → 9000
    # error_pct = 20 → 5500
    # error_pct = 35 → 2500
    # error_pct = 50 → 1000
    # error_pct = 75 → 300
    # error_pct = 100+ → 100

    # Используем экспоненциальное затухание
    score = MAX_SCORE * (0.01 + 0.99 * (1 - min(error_pct, 100) / 100) ** 1.5)
    final_score = round(score)

    # Гарантируем минимум
    final_score = max(MIN_SCORE, final_score)

    if error_pct <= 3:
        result = "perfect"
        hint = "🔥 Идеально!"
    elif error_pct <= 7:
        result = "great"
        hint = "👏 Очень близко!"
    elif error_pct <= 15:
        result = "close"
        hint = "👍 Близко!"
    elif error_pct <= 25:
        result = "decent"
        hint = "🤔 Неплохо"
    elif error_pct <= 40:
        result = "far"
        hint = "😐 Мимо"
    elif error_pct <= 60:
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
        "error_pct": round(error_pct, 1)
    })


# Таблица лидеров
@app.get("/api/leaderboard")
async def leaderboard():
    async with async_session() as session:
        result = await session.execute(
            select(Score).order_by(desc(Score.best_score)).limit(10)
        )
        scores = result.scalars().all()
        return [
            {
                "nickname": s.nickname or f"Игрок {s.user_id[:6]}",
                "best_score": s.best_score,
                "games_played": s.games_played
            }
            for s in scores
        ]


# Сохранить результат
@app.post("/api/save-score")
async def save_score(user_id: str = Body(...), score: float = Body(...)):
    async with async_session() as session:
        existing = await session.get(Score, user_id)
        if existing:
            if score > existing.best_score:
                existing.best_score = score
            existing.games_played += 1
        else:
            existing = Score(user_id=user_id, best_score=score, games_played=1)
            session.add(existing)
        await session.commit()

        top10 = await session.execute(
            select(Score.user_id).order_by(desc(Score.best_score)).limit(10)
        )
        top_ids = [row[0] for row in top10]
        needs_nickname = (user_id in top_ids) and (existing.nickname is None)

        return {"needs_nickname": needs_nickname}


# Установить никнейм
@app.post("/api/nickname")
async def set_nickname(user_id: str = Body(...), nickname: str = Body(...)):
    async with async_session() as session:
        score_obj = await session.get(Score, user_id)
        if score_obj:
            score_obj.nickname = nickname
            await session.commit()
            return {"status": "ok"}
        return {"status": "not_found"}


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
        result = await session.execute(select(Score.best_score))
        all_scores = [row[0] for row in result.all()]

        total = len(all_scores)
        if total == 0:
            return {"percentile": 100, "better_than": 0, "total": 0}

        better_than = sum(1 for s in all_scores if s <= score)
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