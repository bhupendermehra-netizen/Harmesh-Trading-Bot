from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "harmesh-prod-change-me"

    from app.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    return app
