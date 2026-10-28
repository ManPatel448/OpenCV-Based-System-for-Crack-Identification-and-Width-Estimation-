from pathlib import Path

from flask import Flask, jsonify, redirect, request

from config import Config
from models.database import init_db
from routes.analysis_routes import analysis_bp
from routes.history_routes import history_bp
from routes.report_routes import report_bp
from routes.upload_routes import upload_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    Path(app.config["STORAGE_DIR"]).mkdir(parents=True, exist_ok=True)
    for name in ("original", "processed", "annotated", "reports"):
        (Path(app.config["STORAGE_DIR"]) / name).mkdir(exist_ok=True)
    init_db(app)
    app.register_blueprint(upload_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(report_bp)

    @app.get("/")
    def upload_home():
        return redirect("/upload")

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"ok": False, "error": "The upload exceeds the configured size limit."}), 413

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.errorhandler(404)
    def not_found(_error):
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"ok": False, "error": "Resource not found."}), 404
        return "Page not found", 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        debug=False,
        host="127.0.0.1",
        port=5000,
        use_reloader=app.config["AUTO_RELOAD"],
    )
