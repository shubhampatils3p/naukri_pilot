from config import get_default_config
from naukri_bot import NaukriBot

def main():
    config = get_default_config()
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

if __name__ == "__main__":
    main()