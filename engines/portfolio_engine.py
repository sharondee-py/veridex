import requests
from bs4 import BeautifulSoup
import re


class PortfolioEngine:

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.soup = None

    def fetch(self):
        res = requests.get(self.url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            raise Exception("Portfolio not reachable")
        self.soup = BeautifulSoup(res.text, "html.parser")

    def analyse(self):
        self.fetch()

        text = self.soup.get_text(" ", strip=True).lower()

        score = 0
        flags = []

        # -------- Visual professionalism
        images = len(self.soup.find_all("img"))
        if images >= 3:
            score += 10
        else:
            flags.append("Few visuals/screenshots")

        # -------- Project content
        project_words = len(re.findall(r"project|case study|build|system|app", text))
        if project_words >= 5:
            score += 15
        else:
            flags.append("Little project explanation")

        # -------- Tech stack clarity
        tech = len(re.findall(r"python|django|flask|fastapi|sql|linux|docker|api|react|flutter", text))
        if tech >= 5:
            score += 15
        else:
            flags.append("Tech stack weakly presented")

        # -------- Links to proof
        links = self.soup.find_all("a", href=True)
        github_links = [a for a in links if "github.com" in a["href"]]

        if github_links:
            score += 15
        else:
            flags.append("No GitHub links on portfolio")

        # -------- Bio / about
        about = re.search(r"about|who am i|profile|bio", text)
        if about:
            score += 10
        else:
            flags.append("No clear personal intro")

        # -------- Contact presence
        contact = re.search(r"contact|email|linkedin|twitter", text)
        if contact:
            score += 10
        else:
            flags.append("No contact information")

        # -------- Bonus polish heuristic
        title = self.soup.find("title")
        if title and len(title.text.strip()) > 3:
            score += 10

        return {
            "portfolio_score": min(100, score),
            "flags": flags,
            "github_links": len(github_links),
            "screenshots": images,
        }
