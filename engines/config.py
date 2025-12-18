from dotenv import load_dotenv
import os

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Authorization": f"token {os.getenv('GITHUB_TOKEN')}"
}
