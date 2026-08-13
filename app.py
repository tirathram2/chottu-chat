"""Application factory and production entry point for Chottu Chat."""

import os

from flask import Flask, jsonify, render_template, send_from_directory

from auth import auth_bp, login_manager
from config import Config
from database import init_db
from routes import routes_bp
from socket_events import init_socketio, socketio


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."

    init_db(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(routes_bp)

    init_socketio(app)

    @app.route("/robots.txt")
    def robots_txt():
        return (
            "User-agent: *\n"
            "Allow: /\n",
            200,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    @app.route("/google63240b67ab9e0b5e.html")
    def google_verification():
        return send_from_directory(
            app.root_path,
            "google63240b67ab9e0b5e.html",
        )

    @app.errorhandler(404)
    def not_found(_error):
        if app.config.get("TESTING") or app.config.get("DEBUG"):
            return jsonify(error="Not found."), 404

        return (
            render_template(
                "error.html",
                code=404,
                message="Page not found.",
            ),
            404,
        )

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="Files must be smaller than 25 MB."), 413

    @app.errorhandler(500)
    def server_error(_error):
        if app.config.get("TESTING") or app.config.get("DEBUG"):
            return jsonify(error="An unexpected server error occurred."), 500

        return (
            render_template(
                "error.html",
                code=500,
                message="Something went wrong.",
            ),
            500,
        )

    return app


app = create_app()


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=app.config["DEBUG"],
    )
