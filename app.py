from flask import Flask, request, jsonify
from threading import Thread

from main import run_bot  # reuse your existing function

app = Flask(__name__)

def run_bot_background(keyword, location, max_jobs):
    try:
        run_bot(keyword, location, max_jobs)
    except Exception as e:
        print(f"Background run_bot error: {e}")

def parse_apply_command(text: str):
    """
    Parse commands like:
      'Apply for Angular Developer Pune 10'
    into (keyword, location, max_jobs)
    """
    if not text:
        return None

    text = text.strip()
    lower = text.lower()

    if not lower.startswith("apply for "):
        return None

    # Remove the leading 'apply for '
    body = text[len("apply for "):].strip()
    parts = body.split()

    if len(parts) < 3:
        # Need at least: keyword word(s), location, max_jobs
        return None

    # Last token should be max_jobs
    try:
        max_jobs = int(parts[-1])
    except ValueError:
        return None

    # Second last token = location (single word for now)
    location = parts[-2]

    # Everything before that = keyword
    keyword = " ".join(parts[:-2]).strip()

    if not keyword or not location:
        return None

    return keyword, location, max_jobs

@app.route("/trigger", methods=["POST"])
def trigger():
    data = request.get_json() or {}
    keyword = data.get("keyword")
    location = data.get("location")
    max_jobs = int(data.get("max_jobs", 10))

    if not keyword or not location:
        return jsonify({"error": "keyword and location are required"}), 400

    # Start the Selenium bot in a separate thread so HTTP returns quickly
    t = Thread(target=run_bot_background, args=(keyword, location, max_jobs), daemon=True)
    t.start()

    return jsonify({
        "status": "started",
        "keyword": keyword,
        "location": location,
        "max_jobs": max_jobs
    }), 202

@app.route("/command", methods=["POST"])
def command():
    data = request.get_json() or {}
    text = data.get("text", "")

    parsed = parse_apply_command(text)
    if not parsed:
        return jsonify({
            "error": "Invalid command format. Use: 'Apply for <keyword> <location> <max_jobs>'"
        }), 400

    keyword, location, max_jobs = parsed

    # Start bot in background
    t = Thread(target=run_bot_background, args=(keyword, location, max_jobs), daemon=True)
    t.start()

    return jsonify({
        "status": "started",
        "keyword": keyword,
        "location": location,
        "max_jobs": max_jobs
    }), 202

if __name__ == "__main__":
    app.run(port=5000, debug=True)