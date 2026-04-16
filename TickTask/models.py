from extensions import db
from flask_login import UserMixin
from datetime import datetime, timezone

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    tasks = db.relationship('Task', backref='owner', lazy=True)
    statistics = db.relationship('Statistics', backref='user', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Integer, nullable=True)
    importance = db.Column(db.Integer, default=3)
    is_completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Statistics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date(), unique=False)
    completed_count = db.Column(db.Integer, default=0)
    total_tasks = db.Column(db.Integer, default=0)
    productivity_score = db.Column(db.Float, default=0.0)

    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='_user_date_uc'),)