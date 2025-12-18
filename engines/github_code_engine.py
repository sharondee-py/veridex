# engines/github_code_engine.py

import requests
import base64
import re
from collections import Counter
from dotenv import load_dotenv
import os

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Authorization": f"token {os.getenv('GITHUB_TOKEN')}"
}

EXT_LANG = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".dart": "Dart",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".md": "Markdown",
    ".sh": "Shell",
    ".sql": "SQL",
}

CODE_EXTS = set(k for k in EXT_LANG.keys() if k not in {".md", ".json", ".yml", ".yaml"})


class GitHubCodeEngine:
    """
    VeriDex V2 GitHub Code Intelligence
    - Detects repo languages by file extensions
    - Scores repos using language-appropriate heuristics
    - Uses README + tests + structure signals
    """

    def __init__(self, username: str):
        self.username = username
        self.base_api = "https://api.github.com"

    # ---------- API Helpers ----------

    def _get(self, url):
        res = requests.get(url, headers=HEADERS, timeout=25)
        if res.status_code != 200:
            raise Exception(f"GitHub API error: {res.status_code} for {url}")
        return res.json()

    def get_repos(self, max_repos: int = 8):
        """
        V2: analyze more repos, but still finite for performance.
        """
        url = f"{self.base_api}/users/{self.username}/repos?per_page=100&sort=updated"
        repos = self._get(url)

        useful = [
            r for r in repos
            if not r.get("fork", False) and r.get("size", 0) > 0
        ]
        useful.sort(key=lambda r: r.get("pushed_at", ""), reverse=True)
        return useful[:max_repos]

    # ---------- README ----------

    def fetch_readme(self, repo_name: str) -> str:
        url = f"{self.base_api}/repos/{self.username}/{repo_name}/readme"
        try:
            data = self._get(url)
        except Exception:
            return ""

        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return ""

    def analyse_readme(self, text: str) -> dict:
        if not text:
            return {"quality_score": 0}

        lines = text.splitlines()
        words = len(text.split())
        headings = len([l for l in lines if l.strip().startswith("#")])
        code_blocks = len(re.findall(r"```", text))
        has_setup = bool(re.search(r"install|pip|setup|run|docker|flutter|npm|pnpm|yarn|python manage\.py", text, flags=re.I))

        score = 0
        if words >= 80: score += 5
        if headings >= 3: score += 5
        if code_blocks >= 1: score += 5
        if has_setup: score += 5

        return {"quality_score": min(score, 20)}

    # ---------- Repo file walking (multi-language) ----------

    def list_files(self, repo_name: str, path: str = ""):
        """
        Recursively list ALL files in repo via /contents.
        """
        owner = self.username
        url = f"{self.base_api}/repos/{owner}/{repo_name}/contents"
        if path:
            url += f"/{path}"

        items = self._get(url)

        files = []

        if isinstance(items, dict) and items.get("type") == "file":
            files.append(items["path"])
            return files

        for item in items:
            itype = item.get("type")
            ipath = item.get("path")
            if itype == "file":
                files.append(ipath)
            elif itype == "dir":
                files.extend(self.list_files(repo_name, ipath))

        return files

    def fetch_file_content(self, repo_name: str, path: str) -> str:
        owner = self.username
        url = f"{self.base_api}/repos/{owner}/{repo_name}/contents/{path}"
        data = self._get(url)
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return ""

    def detect_languages(self, files: list[str]) -> dict:
        """
        Return language histogram from extensions.
        """
        counts = Counter()
        for p in files:
            lower = p.lower()
            for ext, lang in EXT_LANG.items():
                if lower.endswith(ext):
                    counts[lang] += 1
                    break
        return dict(counts)

    def dominant_language(self, lang_counts: dict) -> str:
        if not lang_counts:
            return "Unknown"
        return max(lang_counts.items(), key=lambda kv: kv[1])[0]

    # ---------- Generic code analysis ----------

    def analyse_python(self, code: str) -> dict:
        lines = code.splitlines()
        return {
            "lines": len(lines),
            "functions": len(re.findall(r"^\s*def\s+", code, re.M)),
            "classes": len(re.findall(r"^\s*class\s+", code, re.M)),
            "imports": len(re.findall(r"^\s*(from|import)\s+", code, re.M)),
            "try_blocks": len(re.findall(r"\btry\s*:", code)),
            "except_blocks": len(re.findall(r"\bexcept\b", code)),
            "comment_lines": len([l for l in lines if l.strip().startswith("#")]),
            "docstrings": len(re.findall(r'"""[\s\S]*?"""', code)) + len(re.findall(r"'''[\s\S]*?'''", code)),
            "api_calls": len(re.findall(r"requests\.|httpx\.|urllib\.", code)),
            "databases": len(re.findall(r"sqlalchemy|psycopg2|sqlite3|pymongo", code, re.I)),
            "frameworks": len(re.findall(r"\bflask\b|\bdjango\b|\bfastapi\b|\bstarlette\b", code, re.I)),
            "async_code": len(re.findall(r"\basync\b|\bawait\b", code)),
        }

    def analyse_js_ts(self, code: str) -> dict:
        lines = code.splitlines()
        return {
            "lines": len(lines),
            "functions": len(re.findall(r"\bfunction\b|\=\s*\(.*?\)\s*=>|\b=>\b", code)),
            "classes": len(re.findall(r"\bclass\s+\w+", code)),
            "imports": len(re.findall(r"^\s*(import\s+|const\s+\w+\s*=\s*require\()", code, re.M)),
            "try_blocks": len(re.findall(r"\btry\s*{", code)),
            "comment_lines": len([l for l in lines if l.strip().startswith("//")]),
            "frameworks": len(re.findall(r"\breact\b|\bnext\b|\bexpress\b|\bnest\b|\bvue\b|\bangular\b", code, re.I)),
            "api_calls": len(re.findall(r"fetch\(|axios\.|superagent\(", code)),
        }

    def analyse_dart(self, code: str) -> dict:
        lines = code.splitlines()
        return {
            "lines": len(lines),
            "classes": len(re.findall(r"\bclass\s+\w+", code)),
            "functions": len(re.findall(r"\b[A-Za-z_]\w*\s*\(.*\)\s*{", code)),  # rough
            "imports": len(re.findall(r"^\s*import\s+'", code, re.M)),
            "frameworks": len(re.findall(r"\bflutter\b|\bmaterial\b|\bcupertino\b|\bprovider\b|\bbloc\b|\briverpod\b", code, re.I)),
            "async_code": len(re.findall(r"\basync\b|\bawait\b", code)),
            "try_blocks": len(re.findall(r"\btry\s*{", code)),
        }

    def analyse_html_css(self, code: str, lang: str) -> dict:
        lines = code.splitlines()
        if lang == "HTML":
            tags = len(re.findall(r"<[a-zA-Z][^>]*>", code))
            return {"lines": len(lines), "tags": tags}
        else:
            selectors = len(re.findall(r"[.#]?[a-zA-Z][\w\-]*\s*{", code))
            return {"lines": len(lines), "selectors": selectors}

    # ---------- Scoring ----------

    def score_repo(self, dominant_lang: str, metrics: dict, readme_score: int, test_files: int) -> int:
        """
        0–100 depth score tuned per dominant language.
        """
        score = 20

        lines = metrics.get("lines", 0)

        # universal: size
        if lines > 150: score += 10
        if lines > 600: score += 10
        if lines > 1500: score += 10

        # universal: tests + readme
        if readme_score >= 10: score += 5
        if readme_score >= 15: score += 5
        if test_files >= 1: score += 5
        if test_files >= 5: score += 5

        if dominant_lang == "Python":
            if metrics.get("functions", 0) >= 5: score += 10
            if metrics.get("classes", 0) >= 2: score += 10
            if metrics.get("imports", 0) >= 5: score += 10
            if metrics.get("frameworks", 0) >= 1: score += 10
            if metrics.get("databases", 0) >= 1: score += 10
            if metrics.get("api_calls", 0) >= 3: score += 5
            if metrics.get("async_code", 0) >= 2: score += 5
            if metrics.get("try_blocks", 0) >= 2: score += 10
            if metrics.get("comment_lines", 0) >= max(8, int(lines * 0.05)): score += 10

        elif dominant_lang in ("JavaScript", "TypeScript"):
            if metrics.get("imports", 0) >= 5: score += 10
            if metrics.get("classes", 0) >= 1: score += 5
            if metrics.get("frameworks", 0) >= 1: score += 10
            if metrics.get("api_calls", 0) >= 2: score += 10
            if metrics.get("try_blocks", 0) >= 1: score += 5
            if metrics.get("comment_lines", 0) >= max(6, int(lines * 0.04)): score += 5

        elif dominant_lang == "Dart":
            if metrics.get("imports", 0) >= 5: score += 10
            if metrics.get("classes", 0) >= 2: score += 10
            if metrics.get("frameworks", 0) >= 2: score += 10
            if metrics.get("async_code", 0) >= 2: score += 5
            if metrics.get("try_blocks", 0) >= 1: score += 5

        elif dominant_lang in ("HTML", "CSS"):
            if lines > 200: score += 10
            if metrics.get("tags", 0) >= 80: score += 10
            if metrics.get("selectors", 0) >= 50: score += 10

        return min(100, score)

    # ---------- Main analysis ----------

    def analyse(self):
        """
        Returns:
        {
          "repos": [ ... ],
          "overall_depth_score": 0-100
        }
        """
        repos = self.get_repos()
        repo_summaries = []

        for repo in repos:
            name = repo["name"]

            try:
                files = self.list_files(name)
            except Exception:
                continue

            if not files:
                continue

            lang_counts = self.detect_languages(files)
            dom_lang = self.dominant_language(lang_counts)

            # tests detection (all langs)
            test_files = [p for p in files if "test" in p.lower() or "tests/" in p.lower()]
            test_count = len(test_files)

            # README
            readme_text = self.fetch_readme(name)
            readme_info = self.analyse_readme(readme_text)
            readme_score = readme_info["quality_score"]

            # choose code files by dominant language
            def match_dom(p: str) -> bool:
                lp = p.lower()
                if dom_lang == "Python": return lp.endswith(".py")
                if dom_lang == "TypeScript": return lp.endswith(".ts") or lp.endswith(".tsx")
                if dom_lang == "JavaScript": return lp.endswith(".js") or lp.endswith(".jsx")
                if dom_lang == "Dart": return lp.endswith(".dart")
                if dom_lang == "HTML": return lp.endswith(".html")
                if dom_lang == "CSS": return lp.endswith(".css") or lp.endswith(".scss")
                return any(lp.endswith(ext) for ext in CODE_EXTS)

            code_files = [p for p in files if match_dom(p)]
            if not code_files:
                # still return repo with low score but track languages
                repo_summaries.append({
                    "name": name,
                    "dominant_language": dom_lang,
                    "language_breakdown": lang_counts,
                    "code_files": 0,
                    "metrics": {"lines": 0},
                    "readme_quality": readme_score,
                    "test_files": test_count,
                    "depth_score": self.score_repo(dom_lang, {"lines": 0}, readme_score, test_count),
                    "html_url": repo.get("html_url"),
                })
                continue

            # combine metrics
            combined = {"lines": 0}

            for path in code_files[:120]:  # safety limit
                try:
                    code = self.fetch_file_content(name, path)
                except Exception:
                    continue

                if dom_lang == "Python":
                    m = self.analyse_python(code)
                elif dom_lang in ("JavaScript", "TypeScript"):
                    m = self.analyse_js_ts(code)
                elif dom_lang == "Dart":
                    m = self.analyse_dart(code)
                elif dom_lang in ("HTML", "CSS"):
                    m = self.analyse_html_css(code, dom_lang)
                else:
                    # fallback: count lines only
                    m = {"lines": len(code.splitlines())}

                # merge
                for k, v in m.items():
                    combined[k] = combined.get(k, 0) + v

            depth = self.score_repo(dom_lang, combined, readme_score, test_count)

            repo_summaries.append({
                "name": name,
                "dominant_language": dom_lang,
                "language_breakdown": lang_counts,
                "code_files": len(code_files),
                "metrics": combined,
                "readme_quality": readme_score,
                "test_files": test_count,
                "depth_score": depth,
                "html_url": repo.get("html_url"),
            })

        if not repo_summaries:
            return {"repos": [], "overall_depth_score": 0}

        top = sorted(repo_summaries, key=lambda r: r.get("depth_score", 0), reverse=True)[:3]
        overall = int(sum(r.get("depth_score", 0) for r in top) / len(top))

        return {"repos": repo_summaries, "overall_depth_score": overall}
