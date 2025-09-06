# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_ckeditor import CKEditor
from flask_migrate import Migrate

db = SQLAlchemy()
ckeditor = CKEditor()
migrate = Migrate()
