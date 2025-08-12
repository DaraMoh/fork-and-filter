import os
from pathlib import Path
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# global DB handle
db = SQLAlchemy()

def create_app():
    load_dotenv()

    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL") or f"sqlite:///{os.path.join(app.instance_path, 'app.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    # ---- PWA files served at root paths ----
    @app.route("/manifest.json")
    def manifest():
        pwa_dir = os.path.join(app.root_path, "pwa")
        return send_from_directory(pwa_dir, "manifest.json", mimetype="application/json")
    
    @app.route("/service-worker.js")
    def service_worker():
        return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    
    @app.route("/icons/<path:filename>")
    def pwa_icons(filename):
        icons_dir = os.path.join(app.root_path, "pwa", "icons")
        return send_from_directory(icons_dir, filename)
    
    # Optional: CLI helper to init the DB quickly
    @app.cli.command("init-db")
    def init_db_command():
        """Create all database tables."""
        with app.app_context():
            db.create_all()
        print("Database initialized")

    return app