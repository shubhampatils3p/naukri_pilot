import os
import time
import requests
from threading import Thread
from config import get_config, TELEGRAM_BOT_TOKEN
from main import run_bot


TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(chat_id: int, text: str):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
        })
    except Exception as e:
        print(f"send_message error: {e}")


def get_updates(offset: int = None, timeout: int = 30):
    params = {
        "timeout": timeout,
        "allowed_updates": ["message"]
    }
    if offset is not None:
        params["offset"] = offset

    try:
        resp = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params=params,
            timeout=(10, timeout + 5)
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    except requests.exceptions.ConnectTimeout as e:
        print(f"get_updates connect timeout: {e}")
        time.sleep(5)
        return []

    except requests.exceptions.ReadTimeout as e:
        print(f"get_updates read timeout: {e}")
        return []

    except requests.exceptions.ConnectionError as e:
        print(f"get_updates connection error: {e}")
        time.sleep(5)
        return []

    except requests.exceptions.RequestException as e:
        print(f"get_updates request error: {e}")
        time.sleep(5)
        return []

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


def run_bot_background(keyword: str, location: str, max_jobs: int, chat_id: int):
    try:
        summary = run_bot(keyword, location, max_jobs)

        applied = summary.get("applied", 0) if summary else 0
        skipped = summary.get("skipped", 0) if summary else 0
        details = summary.get("details", []) if summary else []

        external_skips = [
            d for d in details
            if d.get("reason") in (
                "External company site",
                "Apply on company site",
                "Redirected to company site after apply",
            )
        ]

        lines = [
            f"Finished applying for {keyword} in {location}.",
            "",
            f"Applied: {applied}",
            f"Skipped: {skipped}",
        ]

        if external_skips:
            lines.append("")
            lines.append("Skipped company-site jobs:")
            for i, item in enumerate(external_skips[:15], 1):
                title = item.get("title", "(no title)")
                reason = item.get("reason", "External company site")
                url = item.get("url", "")
                lines.append(f"{i}. {title} | {reason}")
                if url:
                    lines.append(url)

        send_message(chat_id, "\n".join(lines))
    except Exception as e:
        print(f"run_bot_background error: {e}")
        send_message(chat_id, f"Something went wrong: {e}")


def handle_message(message: dict):
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not chat_id:
        return

    parsed = parse_apply_command(text)
    if not parsed:
        send_message(
            chat_id,
            "Invalid command.\n\nUse: Apply for <keyword> ocation> <max_jobs>\n\nExample: Apply for Angular Developer Pune 3"
        )
        return

    keyword, location, max_jobs = parsed

    send_message(chat_id, f"Started applying for {keyword} in {location} (max {max_jobs} jobs).")

    t = Thread(target=run_bot_background, args=(keyword, location, max_jobs, chat_id), daemon=True)
    t.start()


def main():
    print("Telegram bot started. Waiting for messages...")
    offset = None

    while True:
        try:
            updates = get_updates(offset=offset)

            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    handle_message(message)

        except KeyboardInterrupt:
            print("Bot stopped by user.")
            break

        except Exception as e:
            print(f"main loop error: {e}")
            time.sleep(5)

        time.sleep(1)


if __name__ == "__main__":
    main()