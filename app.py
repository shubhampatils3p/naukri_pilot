from flask import Flask, request, jsonify
from threading import Thread
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from config import TWILIO_SID, TWILIO_TOKEN, WHATSAPP_FROM
from main import run_bot 

app = Flask(__name__)
client = Client(TWILIO_SID, TWILIO_TOKEN)

from twilio.rest import Client
from config import TWILIO_SID, TWILIO_TOKEN, WHATSAPP_FROM

client = Client(TWILIO_SID, TWILIO_TOKEN)

def run_bot_background(keyword, location, max_jobs, to_number=None):
    try:
        summary = run_bot(keyword, location, max_jobs)

        if to_number:
            applied = summary.get("applied", 0)
            skipped = summary.get("skipped", 0)

            body = (
                f"Finished applying for {keyword} in {location}.\n\n"
                f"Applied: {applied}\nSkipped: {skipped}"
            )

            client.messages.create(
                from_=WHATSAPP_FROM,  # "whatsapp:+14155238886"
                to=to_number,         # e.g. "whatsapp:+919403851928"
                body=body,
            )
    except Exception as e:
        print(f"Background run_bot error: {e}")

def parse_apply_command(text: str):
    if not text:
        return None

    text = text.strip()
    lower = text.lower()

    if not lower.startswith("apply for "):
        return None

    body = text[len("apply for "):].strip()
    parts = body.split()

    if len(parts) < 3:
        return None

    try:
        max_jobs = int(parts[-1])
    except ValueError:
        return None

    location = parts[-2]
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

@app.route("/whatsapp-test", methods=["POST"])
def whatsapp_test():
    text = request.form.get("Body", "")
    resp = MessagingResponse()

    parsed = parse_apply_command(text)
    if not parsed:
        resp.message("Invalid command. Use: 'Apply for <keyword> <location> <max_jobs>'")
        return str(resp)

    keyword, location, max_jobs = parsed

    from_number = request.form.get("From")
    t = Thread(target=run_bot_background, args=(keyword, location, max_jobs, from_number), daemon=True,)
    t.start()

    resp.message(f"Started applying for {keyword} in {location} (max {max_jobs} jobs).")
    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)