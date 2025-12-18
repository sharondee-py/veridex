import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os
from dotenv import load_dotenv

from .github_code_engine import GitHubCodeEngine
from .portfolio_engine import PortfolioEngine

load_dotenv()

HEADERS = {
    "User-Agent": "VeriDexBot/1.0",
    "Authorization": f"token {os.getenv('GITHUB_TOKEN')}"
}


class GitHubEngine:

    def __init__(self, profile_url, portfolio_url=None):
        self.url = profile_url.rstrip("/")
        self.username = self.url.split("/")[-1].strip().lower()
        self.portfolio_url = portfolio_url
        self.profile_html = None
        self.soup = None
        self.data = {}

    # ---------------- API Helpers ----------------

    def get_api_user(self, username):
        url = f"https://api.github.com/users/{username}"
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200:
            raise Exception("GitHub API unreachable or user not found")
        return res.json()

    def fetch_profile(self):
        res = requests.get(self.url, headers=HEADERS)
        if res.status_code != 200:
            raise Exception("GitHub profile not reachable")
        self.profile_html = res.text
        self.soup = BeautifulSoup(self.profile_html, "html.parser")

    # ---------------- Scraping Extractors ----------------

    def extract_repo_count(self):
        repos = self.soup.find("a", {"href": f"/{self.username}?tab=repositories"})
        if not repos:
            return 0
        match = re.search(r"\d+", repos.text.replace(",", ""))
        return int(match.group()) if match else 0

    def extract_join_date(self):
        api = self.get_api_user(self.username)
        return api.get("created_at")

    def extract_bio(self):
        bio = self.soup.find("div", {"class": "p-note"})
        return bio.text.strip() if bio else None

    def extract_followers(self):
        api = self.get_api_user(self.username)
        return api.get("followers", 0)

    def extract_following(self):
        api = self.get_api_user(self.username)
        return api.get("following", 0)

    # ---------------- Core Metrics ----------------

    def calculate_account_age(self, join_date):
        if not join_date:
            return 0
        join = datetime.fromisoformat(join_date.replace("Z", ""))
        return (datetime.now() - join).days // 365

    def credibility_score_basic(self):
        """
        Score based ONLY on GitHub profile hygiene.
        """
        score = 100

        age = self.data["account_age"]
        repos = self.data["repos"]
        followers = self.data["followers"]

        if age < 1:
            score -= 30
        if repos < 3:
            score -= 25
        if followers < 3:
            score -= 5    # softer
        if not self.data["bio"]:
            score -= 10

        return max(score, 0)

    # ---------------- Dev Maturity ----------------

    def dev_maturity(self, depth_score):
        if depth_score >= 85:
            return "Senior-leaning: strong project depth and consistency"
        elif depth_score >= 65:
            return "Mid-level: solid projects with growing depth"
        elif depth_score >= 45:
            return "Early-stage but promising: real projects, still maturing"
        return "Entry-level / learning phase"

    # ---------------- Recruiter-style Summary ----------------

    def build_recruiter_summary(self, depth_score, portfolio_score, code_report):
        maturity = self.dev_maturity(depth_score)

        repos = code_report.get("repos", []) if isinstance(code_report, dict) else []
        flagship = None
        if repos:
            flagship = sorted(repos, key=lambda r: r.get("depth_score", 0), reverse=True)[0]

        pieces = []

        pieces.append(
            f"{self.username} presents as {maturity.lower()} based on GitHub activity and project depth."
        )

        if flagship:
            name = flagship.get("name", "a flagship repository")
            depth = flagship.get("depth_score", 0)
            lines = flagship.get("metrics", {}).get("lines", 0)
            pieces.append(
                f"The standout project is '{name}', with a depth score of {depth} and roughly {lines} lines of Python code, "
                f"indicating a real-world application rather than a toy script."
            )

        if portfolio_score >= 70:
            pieces.append(
                "The portfolio site clearly explains projects, stack, and contact details, which makes it easy to evaluate and trust this profile."
            )
        elif 40 <= portfolio_score < 70:
            pieces.append(
                "The portfolio gives some insight into the candidate's work, but it could benefit from clearer case studies and visuals."
            )
        else:
            pieces.append(
                "The lack of a strong portfolio presence means most of the signal currently comes from GitHub and code alone."
            )

        followers = self.data.get("followers", 0)
        if followers < 3:
            pieces.append(
                "Social proof on GitHub (followers/stars) is currently low, but the underlying code quality suggests this is more about visibility than skill."
            )

        return {
            "headline": f"{self.username}: {maturity}",
            "summary": " ".join(pieces)
        }

    # ---------------- Main Engine ----------------

    def analyze(self):
        # 1) Core GitHub profile
        self.fetch_profile()

        joined = self.extract_join_date()
        age = self.calculate_account_age(joined)

        self.data = {
            "username": self.username,
            "joined": joined,
            "account_age": age,
            "repos": self.extract_repo_count(),
            "followers": self.extract_followers(),
            "following": self.extract_following(),
            "bio": self.extract_bio(),
            "portfolio_url": self.portfolio_url,
        }

        base_score = self.credibility_score_basic()

        # 2) Code Intelligence
        try:
            code_engine = GitHubCodeEngine(self.username)
            code_report = code_engine.analyse()
        except Exception as e:
            code_report = {"error": f"Code analysis failed: {str(e)}"}

        self.data["code_intel"] = code_report
        depth_score = code_report.get("overall_depth_score", 0)
        self.data["code_credibility"] = depth_score

        # 3) Portfolio Intelligence
        if self.portfolio_url:
            try:
                p_engine = PortfolioEngine(self.portfolio_url)
                portfolio_report = p_engine.analyse()
            except Exception as e:
                portfolio_report = {"error": f"Portfolio analysis failed: {str(e)}"}
        else:
            portfolio_report = {"notice": "No portfolio provided"}

        self.data["portfolio"] = portfolio_report
        portfolio_score = portfolio_report.get("portfolio_score", 0)

        # 4) Final Score Merge
        final_score = int(
            (0.45 * base_score) +       # profile hygiene
            (0.40 * depth_score) +      # code depth
            (0.15 * portfolio_score)    # portfolio clarity
        )
        final_score = max(0, min(100, final_score))
        self.data["credibility_score"] = final_score

        # 5) Dev Maturity + Recruiter Summary
        maturity_label = self.dev_maturity(depth_score)
        self.data["dev_maturity"] = maturity_label

        summary = self.build_recruiter_summary(depth_score, portfolio_score, code_report)
        self.data["headline"] = summary["headline"]
        self.data["summary"] = summary["summary"]

        # 6) Red Flags
        self.data["flags"] = self.red_flags()

        return self.data

    # ---------------- Red Flags ----------------

    def red_flags(self):
        flags = []

        if self.data["account_age"] < 1:
            flags.append("Very new GitHub account")

        if self.data["repos"] == 0:
            flags.append("No public repositories")

        if not self.data["bio"]:
            flags.append("No profile bio")

        if self.data["followers"] < 2:
            flags.append("Very low follower trust")

        return flags
