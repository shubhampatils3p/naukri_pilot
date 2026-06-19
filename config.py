from dataclasses import dataclass

@dataclass
class NaukriConfig:
    email: str
    password: str
    keyword: str
    location: str
    max_jobs: int = 10

def get_default_config() -> NaukriConfig:
    # You can hardcode tonight; later we can move to .env or CLI args
    return NaukriConfig(
        email="email",
        password="password",
        keyword="Angular Developer",
        location="Pune",
        max_jobs=10,
    )