from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
import random

from models import init_db, async_session, Score
from facts import FACTS

app = FastAPI()

# Подключаем папки со статикой и шаблонами
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup():
    await init_db()


# Главная страница
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


# Получить случайный вопрос
@app.get("/api/question")
async def get_question():
    fact = random.choice(FACTS)
    return {
        "question": fact["question"],
        "unit": fact["unit"],
        "fact_id": FACTS.index(fact)
    }


# Проверить ответ
@app.post("/api/check")
async def check_answer(fact_id: int = Body(...), user_answer: float = Body(...)):
    fact = FACTS[fact_id]
    correct = fact["answer"]
    error_pct = abs(user_answer - correct) / correct * 100

    if error_pct <= 5:
        result = "perfect"
        message = f"🎯 Идеально! {fact['comparison']}"
        points = 100
    elif error_pct <= 20:
        result = "close"
        message = f"👍 Близко! {fact['comparison']}"
        points = 50
    elif error_pct <= 50:
        result = "far"
        message = f"🤔 Мимо. Правильный ответ: {correct} {fact['unit']}. {fact['comparison']}"
        points = 10
    else:
        result = "miss"
        message = f"😱 Вообще не угадали! {correct} {fact['unit']}. {fact['comparison']}"
        points = 0

    hint = fact["hint_low"] if user_answer < correct else fact["hint_high"]

    return JSONResponse({
        "result": result,
        "message": message,
        "hint": hint,
        "correct_answer": correct,
        "points": points,
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