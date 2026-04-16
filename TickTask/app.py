import os
import json
import openai
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone

load_dotenv()

from extensions import db, login_manager
from models import User, Task, Category, Statistics

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_fallback_secret_key_change_me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ticktask.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
if not deepseek_api_key:
    print(
        "!!! ВНИМАНИЕ: Ключ DeepSeek API (DEEPSEEK_API_KEY) не найден в файле .env. ИИ-функции не будут работать. !!!")

client = openai.OpenAI(
    api_key=deepseek_api_key,
    base_url="https://api.deepseek.com/v1"
)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def update_statistics(user_id, completed_today=False, new_task_added=False):
    today = datetime.now(timezone.utc).date()
    stats = Statistics.query.filter_by(user_id=user_id, date=today).first()

    if not stats:
        stats = Statistics(user_id=user_id, date=today)
        db.session.add(stats)
        db.session.flush()

    if new_task_added:
        stats.total_tasks += 1
    if completed_today:
        stats.completed_count += 1

    if stats.total_tasks > 0:
        stats.productivity_score = (stats.completed_count / stats.total_tasks) * 100
    else:
        stats.productivity_score = 0.0

    db.session.commit()


def ai_parse_task(text):
    if not deepseek_api_key:
        print("DeepSeek API key is not set. Cannot parse task.")
        return {
            "title": text,
            "due_date": None,
            "category_id": None,
            "importance": 3,
            "duration": 30
        }

    try:
        prompt = f"""
        Извлеки из следующего текста задачи: название, дату, время, категорию, предполагаемую длительность и важность.
        Верни результат ТОЛЬКО в формате JSON. Не добавляй никаких других слов или объяснений.
        Если информация отсутствует, используй null для даты и времени, 'Другое' для категории, 3 для важности и 30 для длительности.
        Список категорий: Работа, Учеба, Личное, Спорт, Здоровье, Дом, Другое.
        Важность: число от 1 (низкая) до 5 (высокая).
        Длительность: число в минутах.
        Формат даты: YYYY-MM-DD. Формат времени: HH:MM.

        Текст задачи: "{text}"

        Пример JSON для задачи 'Встреча с коллегой завтра в 10:00, работа, важность 4, 60 мин':
        {{
            "title": "Встреча с коллегой",
            "date": "{(datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%d')}",
            "time": "10:00",
            "category": "Работа",
            "importance": 4,
            "duration": 60
        }}

        JSON:
        """

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system",
                 "content": "Ты — умный ассистент, который извлекает информацию из текста задач и возвращает ее в строгом JSON формате."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=250,
            response_format={"type": "json_object"}
        )

        ai_response_text = response.choices[0].message.content
        ai_data = json.loads(ai_response_text)

        due_date = None
        if ai_data.get('date'):
            try:
                date_str = ai_data['date']
                time_str = ai_data.get('time')
                dt_format = "%Y-%m-%d"
                if time_str:
                    dt_format += " %H:%M"
                    dt_string = f"{date_str} {time_str}"
                else:
                    dt_string = date_str

                due_date = datetime.strptime(dt_string, dt_format)
            except ValueError:
                print(f"Ошибка парсинга даты/времени из ИИ: {date_str} {time_str}")
                pass

        category_name = ai_data.get('category', 'Другое')
        category = Category.query.filter_by(name=category_name).first()
        if not category:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.commit()

        return {
            "title": ai_data.get('title', text),
            "due_date": due_date,
            "category_id": category.id if category else None,
            "importance": int(ai_data.get('importance', 3)),
            "duration": int(ai_data.get('duration', 30))
        }

    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON от DeepSeek API: {ai_response_text}")
    except Exception as e:
        print(f"Ошибка при работе с DeepSeek API: {e}")

    return {
        "title": text,
        "due_date": None,
        "category_id": Category.query.filter_by(name='Другое').first().id if Category.query.filter_by(
            name='Другое').first() else None,
        "importance": 3,
        "duration": 30
    }


def get_ai_scheduled_tasks(user_id):
    if not deepseek_api_key:
        return []

    user_tasks = Task.query.filter_by(user_id=user_id, is_completed=False).order_by(Task.due_date.asc().nulls_last(),
                                                                                    Task.importance.desc()).all()

    prompt_tasks_list = []
    for task in user_tasks:
        task_info = f"- Задача: '{task.title}', Важность: {task.importance}, Длительность: {task.duration} мин."
        if task.due_date:
            due_dt_utc = task.due_date.astimezone(timezone.utc) if task.due_date.tzinfo else task.due_date.replace(
                tzinfo=timezone.utc)
            task_info += f", Срок: {due_dt_utc.strftime('%Y-%m-%d %H:%M UTC')}"
        prompt_tasks_list.append(task_info)

    userrs_taskss = '\n'.join(prompt_tasks_list)
    prompt = f"""
    Составь оптимальное расписание на ближайшие 24 часа для пользователя, учитывая его невыполненные задачи.
    Задачи должны быть отсортированы по важности и срочности.
    Учитывай длительность каждой задачи.
    Верни расписание в виде списка JSON объектов, где каждый объект имеет поля "task_title", "start_time", "end_time".
    Время должно быть в формате 'YYYY-MM-DD HH:MM'.
    Начинай расписание с текущего момента, если это возможно.

    Задачи пользователя:
    {userrs_taskss}

    Текущее время (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}

    JSON Расписание:
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system",
                 "content": "Ты — ассистент по планированию расписания, который генерирует расписание в строгом JSON формате."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=700,
            response_format={"type": "json_object"}
        )

        ai_response_text = response.choices[0].message.content
        scheduled_tasks = json.loads(ai_response_text)

        for task_entry in scheduled_tasks:
            try:
                task_entry['start_time'] = datetime.strptime(task_entry['start_time'], '%Y-%m-%d %H:%M')
                task_entry['end_time'] = datetime.strptime(task_entry['end_time'], '%Y-%m-%d %H:%M')
            except (KeyError, ValueError):
                print(f"Ошибка парсинга даты/времени в расписании: {task_entry}")
                task_entry['start_time'] = None
                task_entry['end_time'] = None

        return [t for t in scheduled_tasks if t['start_time'] and t['end_time']]
    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON от API при планировании: {ai_response_text}")
    except Exception as e:
        print(f"Ошибка при умном планировании с DeepSeek API: {e}")
    return []


@app.route('/')
@login_required
def index():
    tasks = Task.query.filter_by(user_id=current_user.id, is_completed=False).order_by(Task.due_date.asc().nulls_last(),
                                                                                       Task.importance.desc()).all()
    categories = Category.query.all()
    return render_template('index.html', tasks=tasks, categories=categories)


@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    raw_text = request.form.get('task_text')
    if raw_text:
        ai_data = ai_parse_task(raw_text)
        new_task = Task(
            title=ai_data['title'],
            due_date=ai_data['due_date'],
            category_id=ai_data['category_id'],
            importance=ai_data['importance'],
            duration=ai_data['duration'],
            user_id=current_user.id
        )
        db.session.add(new_task)
        db.session.commit()

        update_statistics(current_user.id, new_task_added=True)
        flash('Задача добавлена и обработана ИИ!', 'success')
    else:
        flash('Поле задачи не может быть пустым.', 'danger')
    return redirect(url_for('index'))


@app.route('/task/<int:task_id>/complete', methods=['POST'])
@login_required
def complete_task(task_id):
    task = db.session.get(Task, task_id)
    if task and task.user_id == current_user.id:
        task.is_completed = True
        db.session.commit()
        update_statistics(current_user.id, completed_today=True)
        flash('Задача отмечена как выполненная!', 'success')
    else:
        flash('У вас нет прав на изменение этой задачи или задача не найдена.', 'danger')
    return redirect(url_for('index'))


@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
        flash('Задача удалена.', 'info')
    else:
        flash('У вас нет прав на удаление этой задачи или задача не найдена.', 'danger')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Вы уже вошли в систему.', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('Пожалуйста, заполните все поля.', 'warning')
            return render_template('register.html', form_data=request.form)

        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято.', 'danger')
            return render_template('register.html', form_data=request.form)

        if password != confirm_password:
            flash('Пароли не совпадают.', 'danger')
            return render_template('register.html', form_data=request.form)

        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация прошла успешно! Теперь войдите в систему.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('Вы уже вошли в систему.', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Добро пожаловать, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы.', 'info')
    return redirect(url_for('login'))


@app.route('/schedule')
@login_required
def schedule():
    scheduled_tasks = get_ai_scheduled_tasks(current_user.id)
    return render_template('schedule.html', scheduled_tasks=scheduled_tasks)


@app.route('/statistics')
@login_required
def statistics():
    today = datetime.now(timezone.utc).date()
    week_ago = today - timedelta(days=7)

    weekly_stats = Statistics.query.filter(
        Statistics.user_id == current_user.id,
        Statistics.date >= week_ago,
        Statistics.date <= today
    ).order_by(Statistics.date).all()

    dates = [stat.date.strftime('%d.%m') for stat in weekly_stats]
    productivity_scores = [stat.productivity_score for stat in weekly_stats]

    motivational_report = ""
    if weekly_stats:
        avg_productivity = sum(s.productivity_score for s in weekly_stats) / len(weekly_stats) if weekly_stats else 0
        total_completed = sum(s.completed_count for s in weekly_stats)
        total_tasks_week = sum(s.total_tasks for s in weekly_stats)

        motivational_report += f"Ваша средняя продуктивность за неделю составила {avg_productivity:.1f}%. "
        if avg_productivity > 70:
            motivational_report += "Отличная работа! Вы держите темп. "
        elif avg_productivity > 50:
            motivational_report += "Хороший результат! Продолжайте в том же духе. "
        else:
            motivational_report += "Есть куда стремиться, но вы на правильном пути! "

        motivational_report += f"Всего за неделю вы выполнили {total_completed} из {total_tasks_week} запланированных задач."
    else:
        motivational_report = "На этой неделе вы еще не накопили статистику. Начните добавлять и выполнять задачи!"

    return render_template('statistics.html',
                           weekly_stats=weekly_stats,
                           dates=dates,
                           productivity_scores=productivity_scores,
                           motivational_report=motivational_report)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Category.query.first():
            print("Создание стандартных категорий...")
            default_categories = ["Работа", "Учеба", "Личное", "Спорт", "Здоровье", "Дом", "Другое"]
            for name in default_categories:
                if not Category.query.filter_by(name=name).first():
                    db.session.add(Category(name=name))
            db.session.commit()
            print("Стандартные категории созданы.")

    app.run(debug=True)
