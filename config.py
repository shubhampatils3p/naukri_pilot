from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

# get the environment variables for Twilio and Naukri credentials
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
WHATSAPP_FROM = os.getenv("WHATSAPP_FROM")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")


@dataclass
class NaukriConfig:
    email: str
    password: str
    keyword: str
    location: str
    max_jobs: int = 5

def get_config(keyword: str, location: str, max_jobs: int) -> NaukriConfig:
    return NaukriConfig(
        email=EMAIL,
        password=PASSWORD,
        keyword=keyword,
        location=location,
        max_jobs=max_jobs,
    )