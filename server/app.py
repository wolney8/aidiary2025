# [stub] Flask app factory + health check
from flask import Flask, jsonify
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app)
    @app.get("/health")
    def health():
        return jsonify(status="ok")
    return app

app = create_app()
