import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GITHUB_PAT: str = os.getenv("GITHUB_PAT", "")

settings = Settings()

# Configuration settings will be defined here
# For example, API keys, database URLs, etc. 