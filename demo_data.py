"""Demo data helpers: seed realistic sample history and reset the shared demo space."""
import json
import random
from datetime import datetime, timedelta

from db import drop_tables, get_connection, init_db

SAMPLE_GOAL = "Lose 10 lbs before summer while balancing Pitta dosha through diet."

_MEALS = [
    ("Oatmeal with stewed apples, cinnamon and ghee", 380),
    ("Moong dal khichdi with cucumber raita", 520),
    ("Quinoa salad with chickpeas, mint and lime", 450),
    ("Vegetable upma with coconut chutney", 410),
    ("Grilled paneer tikka with sautéed greens", 560),
    ("Spicy chicken curry with naan", 820),
    ("Coconut rice with steamed vegetables", 490),
    ("Pizza slice and soda", 710),
    ("Mung bean soup with basmati rice", 470),
    ("Fruit bowl with soaked almonds", 290),
]


def seed_sample_data(days: int = 14) -> str:
    """Inserts ~2 weeks of biometrics, meals and an active goal."""
    rng = random.Random(42)
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().replace(minute=0, second=0, microsecond=0)

    cur.execute("SELECT COUNT(*) FROM user_goals WHERE goal = ?", (SAMPLE_GOAL,))
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO user_goals (goal, created_at) VALUES (?, ?)",
            (SAMPLE_GOAL, (now - timedelta(days=days)).isoformat(" ")),
        )

    weight, fat = 176.2, 26.1
    for d in range(days, 0, -1):
        day = now - timedelta(days=d)
        weight += rng.uniform(-0.55, 0.25)
        fat += rng.uniform(-0.15, 0.06)
        tags = {"BMI": "High" if weight > 170 else "Standard", "Body Fat": "High" if fat > 24 else "Acceptable"}
        cur.execute(
            """INSERT INTO biometrics (timestamp, weight_lb, bmi, metabolic_age, bmr_kcal,
               body_fat_percentage, visceral_fat_rating, skeletal_muscle_percentage,
               muscle_mass_lb, body_water_percentage, protein_percentage, status_tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                day.replace(hour=7).isoformat(" "), round(weight, 1), round(weight / 6.87, 1), 38,
                1680, round(fat, 1), 9, 48.0, round(weight * 0.717, 1), 54.8, 17.5, json.dumps(tags),
            ),
        )
        for hour in (8, 13):
            items, cal = rng.choice(_MEALS)
            cur.execute(
                "INSERT INTO meals (timestamp, items, calories, notes) VALUES (?, ?, ?, ?)",
                (day.replace(hour=hour).isoformat(" "), items, cal, "Sample data"),
            )

    conn.commit()
    conn.close()
    return f"Loaded {days} days of sample biometrics and meals, plus a sample goal."


def reset_demo(memory, thread_id: str) -> None:
    """Wipes all tables and the agent's conversation memory."""
    drop_tables()
    init_db()
    try:
        memory.delete_thread(thread_id)
    except Exception:
        pass
