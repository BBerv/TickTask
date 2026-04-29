import sqlalchemy
from sqlalchemy import orm
import datetime
from .db_session import SqlAlchemyBase


class Tasks(SqlAlchemyBase):
    __tablename__ = 'tasks'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    title = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    content = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    # Поля, которые заполнит ИИ:
    category = sqlalchemy.Column(sqlalchemy.String, default="Общее")
    priority = sqlalchemy.Column(sqlalchemy.Integer, default=1)  # 1-Низкий, 3-Высокий
    due_date = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # Дата/время выполнения
    duration = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # Длительность

    is_finished = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    file_path = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    # Для статистики
    created_date = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now)
    finished_date = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"))
    user = orm.relationship('User')