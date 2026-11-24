from app import app


@app.route("/test-only")
def test_only():
    return "ok"
