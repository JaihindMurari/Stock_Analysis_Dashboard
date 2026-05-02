"""
NSE Dashboard - Flask Application Factory
Production-ready Indian Equity Market Analysis Dashboard
"""
import logging
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name=None):
    """Application factory pattern."""
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # ── Configuration ──────────────────────────────────────────────────────────
    db_user     = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'password')
    db_host     = os.getenv('DB_HOST', 'localhost')
    db_port     = os.getenv('DB_PORT', '3306')
    db_name     = os.getenv('DB_NAME', 'nse_dashboard')

    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key'),
        SQLALCHEMY_DATABASE_URI=(
            f"mysql+pymysql://{db_user}:{db_password}"
            f"@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_size': 10,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
        },
        JSON_SORT_KEYS=False,
    )

    # ── Extensions ─────────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)

    # ── Logging ────────────────────────────────────────────────────────────────
    logging.basicConfig(
        level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # ── Blueprints ─────────────────────────────────────────────────────────────
    from app.routes.main      import main_bp
    from app.routes.api       import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # ── Scheduler ──────────────────────────────────────────────────────────────
    from app.services.scheduler import init_scheduler
    init_scheduler(app)

    return app
