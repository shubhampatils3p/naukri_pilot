from dataclasses import dataclass

@dataclass
class NaukriConfig:
    email: str
    password: str
    keyword: str
    location: str
    max_jobs: int = 5

def get_config(keyword: str, location: str, max_jobs: int) -> NaukriConfig:
    return NaukriConfig(
        email="shubhampatils3p@gmail.com",
        password="Pushprakash@1501",
        keyword=keyword,
        location=location,
        max_jobs=max_jobs,
    )