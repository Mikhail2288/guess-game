import os
from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./game.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Убираем sslmode=require, asyncpg всегда использует SSL для Neon
if "sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?sslmode=require", "")
    DATABASE_URL = DATABASE_URL.replace("&sslmode=require", "")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Score(Base):
    __tablename__ = "scores"
    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nickname = Column(String, nullable=True)
    best_score = Column(Float, default=0)
    games_played = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fact_id = Column(Integer, nullable=False)
    user_answer = Column(Float, nullable=False)
    correct_answer = Column(Float, nullable=False)
    points = Column(Integer, nullable=False)
    user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

class Suggestion(Base):
    __tablename__ = "suggestions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(String, nullable=False)
    answer = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    email = Column(String, nullable=True)  # ← добавить
    created_at = Column(DateTime, default=datetime.utcnow)

class Feedback(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String, nullable=False)
    email = Column(String, nullable=True)  # ← добавить
    created_at = Column(DateTime, default=datetime.utcnow)