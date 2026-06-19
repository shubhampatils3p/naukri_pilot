from config import get_config
from naukri_bot import NaukriBot

def run_bot(keyword: str, location: str, max_jobs: int):
    config = get_config(keyword, location, max_jobs)
    print("Using config:", config)

    bot = NaukriBot(config, headless=False)
    try:
        print("Logging in...")
        bot.login()
        print("Logged in, starting search...")
        bot.search_jobs()
        print("Search loaded, applying...")
        bot.apply_to_jobs()
    finally:
        bot.quit()