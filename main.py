import os
import datetime
from flask import Flask, render_template, redirect, request, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from data import db_session
from data.users import User
from data.tasks import Tasks
from api.tasks_api import blueprint as tasks_blueprint, parse_task_ai, get_smart_plan
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ticktask_secure_key_v4'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Регистрация API
app.register_blueprint(tasks_blueprint)

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# ИСПРАВЛЕНИЕ: Эта строка перенаправляет на страницу входа при попытке доступа без авторизации
login_manager.login_view = 'login'
login_manager.login_message = "Пожалуйста, войдите в систему, чтобы увидеть эту страницу."


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove_session()


# --- МАРШРУТЫ АВТОРИЗАЦИИ ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db_sess = db_session.create_session()
        # Проверка, нет ли уже такого пользователя
        if db_sess.query(User).filter(User.email == request.form.get('email')).first():
            return render_template('register.html', error="Такой email уже зарегистрирован")

        user = User(
            name=request.form.get('name'),
            email=request.form.get('email')
        )
        user.set_password(request.form.get('password'))
        db_sess.add(user)
        db_sess.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        return render_template('login.html', error="Неправильный логин или пароль")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# --- ОСНОВНЫЕ МАРШРУТЫ ПРИЛОЖЕНИЯ ---

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('index.html', tasks=[])
    db_sess = db_session.create_session()
    tasks = db_sess.query(Tasks).filter(Tasks.user_id == current_user.id) \
        .order_by(Tasks.is_finished, Tasks.priority.desc()).all()
    reminders = [t for t in tasks if not t.is_finished and t.priority == 3]
    return render_template('index.html', tasks=tasks, reminders=reminders)


@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        raw_date = request.form.get('due_date')

        # Форматирование даты
        try:
            date_obj = datetime.datetime.strptime(raw_date, '%Y-%m-%d')
            due_date = date_obj.strftime('%d.%m.%Y')
        except:
            due_date = "Не указан"

        # Работа ИИ
        ai_data = parse_task_ai(title)

        db_sess = db_session.create_session()
        task = Tasks(
            title=title, content=content,
            category=ai_data.get('category'),
            priority=ai_data.get('priority'),
            due_date=due_date,
            duration=ai_data.get('duration'),
            user_id=current_user.id
        )

        file = request.files.get('file')
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            task.file_path = f"/static/uploads/{filename}"

        db_sess.add(task)
        db_sess.commit()
        return redirect(url_for('index'))
    return render_template('edit_task.html')


@app.route('/complete/<int:id>')
@login_required
def complete(id):
    db_sess = db_session.create_session()
    task = db_sess.query(Tasks).filter(Tasks.id == id, Tasks.user_id == current_user.id).first()
    if task:
        task.is_finished = True
        db_sess.commit()
    return redirect(url_for('index'))


@app.route('/plan')
@login_required
def plan():
    db_sess = db_session.create_session()
    tasks = db_sess.query(Tasks).filter(Tasks.user_id == current_user.id, Tasks.is_finished == False).all()
    ai_plan = get_smart_plan(tasks)
    return render_template('plan.html', plan=ai_plan)


@app.route('/stats')
@login_required
def stats():
    db_sess = db_session.create_session()
    all_t = db_sess.query(Tasks).filter(Tasks.user_id == current_user.id).all()
    done = [t for t in all_t if t.is_finished]
    percent = (len(done) / len(all_t) * 100) if all_t else 0
    return render_template('stats.html', total=len(all_t), done=len(done), percent=int(percent))


if __name__ == '__main__':
    if not os.path.exists('db'): os.makedirs('db')
    if not os.path.exists('static/uploads'): os.makedirs('static/uploads')
    db_session.global_init("db/tasks.sqlite")
    app.run(port=8080, host='127.0.0.1')