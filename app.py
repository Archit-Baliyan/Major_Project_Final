"""Smart Attendance and Analytics System - Flask application entry point.

Run with:  python app.py   (then open http://127.0.0.1:5000)
"""
import mysql.connector
from flask import Flask, render_template

from config import Config
from utils import db
from utils.auth import csrf_protect, csrf_token


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    app.teardown_appcontext(db.close_db)      # close DB connection after every request
    app.before_request(csrf_protect)          # CSRF check on every POST
    app.jinja_env.globals["csrf_token"] = csrf_token

    from routes.admin import bp as admin_bp
    from routes.auth import bp as auth_bp
    from routes.student import bp as student_bp
    from routes.teacher import bp as teacher_bp
    for blueprint in (auth_bp, admin_bp, teacher_bp, student_bp):
        app.register_blueprint(blueprint)

    @app.after_request
    def no_cache(resp):
        # stops the browser "Back" button from showing private pages after logout
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    def show_error(code, title, message):
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return show_error(400, "Bad request", getattr(e, "description", "The request could not be processed."))

    @app.errorhandler(403)
    def forbidden(_e):
        return show_error(403, "Access denied", "You do not have permission to open this page.")

    @app.errorhandler(404)
    def not_found(_e):
        return show_error(404, "Page not found", "The page you are looking for does not exist.")

    @app.errorhandler(mysql.connector.Error)
    def db_error(e):
        app.logger.exception("Database error")
        return show_error(500, "Database error",
                          "Could not talk to MySQL. Check that MySQL is running and that the "
                          "credentials in your .env file are correct.")

    @app.errorhandler(500)
    def server_error(_e):
        return show_error(500, "Something went wrong", "An unexpected error occurred. Please try again.")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
