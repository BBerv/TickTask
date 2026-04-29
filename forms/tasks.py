from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import DataRequired


class TaskForm(FlaskForm):
    title = StringField('Заголовок задачи', validators=[DataRequired()])
    content = TextAreaField('Описание задачи')

    # Поле для загрузки файла. Можно ограничить расширения (jpg, pdf, txt и т.д.)
    file = FileField('Прикрепить файл', validators=[
        FileAllowed(['jpg', 'png', 'pdf', 'txt', 'zip', 'docx'], 'Только документы и изображения!')
    ])

    is_finished = BooleanField('Задача завершена')
    submit = SubmitField('Сохранить')