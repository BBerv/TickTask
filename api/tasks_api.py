import flask
import json
from groq import Groq

API_KEY = "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"
client = Groq(api_key=API_KEY)
blueprint = flask.Blueprint('tasks_api', __name__)


def parse_task_ai(text):
    prompt = f"""
    Проанализируй задачу: "{text}"

    1. КАТЕГОРИЯ: Выбери одну (Работа, Учеба, Быт, Здоровье, Другое).
    2. ВАЖНОСТЬ: Оцени от 1 до 3 звезд (3 — критично/дедлайн, 2 — важно, 1 — мелочь).
    3. ВРЕМЯ: Оцени, сколько примерно минут или часов займет выполнение.

    ВЕРНИ СТРОГО JSON:
    {{
        "category": "Название",
        "priority": Число,
        "duration": "Время (например: 45 мин или 2 часа)"
    }}
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"category": "Другое", "priority": 1, "duration": "30 мин"}


def get_smart_plan(tasks_list):
    if not tasks_list: return "Нет активных задач."
    tasks_info = "\n".join([f"- {t.title} ({t.duration}, важность: {t.priority}*)" for t in tasks_list])
    prompt = f"Составь план дня на русском для этих задач:\n{tasks_info}"
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except:
        return "Ошибка планирования."