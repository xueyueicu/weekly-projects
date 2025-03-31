from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # 注册蓝图
    from app.views.auth import auth_bp
    from app.views.student import student_bp
    from app.views.club import club_bp
    from app.views.admin import admin_bp
    from app.views.main import main_bp
    from flask import render_template

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(club_bp, url_prefix='/club')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(main_bp)

    # 如果需要定时任务也可以在此进行初始化

    return app