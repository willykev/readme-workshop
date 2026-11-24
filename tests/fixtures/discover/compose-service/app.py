import os

import psycopg
from flask import Flask, jsonify, request

app = Flask(__name__)


def _private_helper():
    return psycopg.connect(os.environ.get("DATABASE_URL", ""))


@app.route("/")
def index():
    return jsonify(name="shelf")


@app.route("/items", methods=["GET", "POST"])
def items():
    if request.method == "POST":
        return jsonify(created=True), 201
    return jsonify(items=[])


@app.delete("/items/<int:item_id>")
def delete_item(item_id):
    return "", 204


@app.get("/health")
def health():
    return jsonify(ok=True, level=os.getenv("LOG_LEVEL", "info"))


# @app.route("/admin")
# def admin():
#     return "secret"
