import csv
import random
from pathlib import Path

FACTS = []

def load_facts():
    global FACTS
    csv_path = Path(__file__).parent / "facts.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            FACTS.append({
                "question": row["question"],
                "answer": float(row["answer"]),
                "unit": row["unit"],
                "image_url": row.get("image_url", "")  # может быть пустым
            })

def get_random_fact():
    return random.choice(FACTS)

def get_fact_by_id(fact_id):
    return FACTS[fact_id]

# Загружаем факты при импорте
load_facts()