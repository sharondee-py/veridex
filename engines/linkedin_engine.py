import re
import requests
from pypdf import PdfReader
from io import BytesIO


TECH_SKILLS = {
    "python", "javascript", "django", "flask", "fastapi", "c++", "dart",
    "html", "css", "json", "sql", "linux", "git", "react", "flutter",
    "cybersecurity", "networking", "mis"
}

LANGUAGE_HINTS = ["native", "fluent", "working", "elementary", "basic", "limited"]


class LinkedInEngine:
    """
    LinkedIn Intelligence Engine (V3 – Explainable)
    - PDF-first analysis
    - Headerless detection
    - Resume-layout aware
    """

    def __init__(self, linkedin_url: str = None, pdf_bytes: bytes = None):
        self.url = linkedin_url
        self.pdf_bytes = pdf_bytes

    def analyze(self):
        if self.pdf_bytes:
            return self._analyze_pdf(self.pdf_bytes)

        if not self.url:
            return {"notice": "No LinkedIn provided"}

        # URL scan is best-effort only
        try:
            res = requests.get(
                self.url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            if res.status_code != 200:
                raise Exception("Blocked")
        except Exception:
            return {
                "mode": "url_failed",
                "linkedin_score": 0,
                "flags": ["LinkedIn blocks automated profile access"],
                "hint": "Upload LinkedIn PDF for full analysis"
            }

        return {
            "mode": "url_basic",
            "linkedin_score": 10,
            "flags": ["Limited insight from URL scan"],
        }

    # ---------------- PDF ANALYSIS ---------------- #

    def _analyze_pdf(self, pdf_bytes: bytes):
        reader = PdfReader(BytesIO(pdf_bytes))
        pages = [p.extract_text() or "" for p in reader.pages]
        raw_text = "\n".join(pages)
        text = re.sub(r"[ \t]+", " ", raw_text)

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        sections = {
            "headline": None,
            "skills": [],
            "certifications": [],
            "education": [],
            "languages": [],
            "experience": [],
        }

        # ---------- HEADLINE ----------
        if lines:
            sections["headline"] = " | ".join(lines[:3])

        # ---------- SKILLS ----------
        for line in lines:
            tokens = {t.lower().strip(",|") for t in re.split(r"[•,|/]", line)}
            matched = tokens & TECH_SKILLS
            if len(matched) >= 1:
                sections["skills"].extend(sorted(matched))

        sections["skills"] = sorted(set(sections["skills"]))

        # ---------- CERTIFICATIONS ----------
        for line in lines:
            if re.search(r"certified|certification|specialization|expert", line, re.I):
                if len(line) > 10:
                    sections["certifications"].append(line)

        # ---------- EDUCATION ----------
        for i, line in enumerate(lines):
            if re.search(r"university|college|institute|bsc|msc|master", line, re.I):
                block = " ".join(lines[i:i+2])
                sections["education"].append(block)

        # ---------- LANGUAGES ----------
        for line in lines:
            if any(h in line.lower() for h in LANGUAGE_HINTS):
                sections["languages"].append(line)

        # ---------- EXPERIENCE (light) ----------
        for line in lines:
            if re.search(r"developer|engineer|intern|analyst", line, re.I):
                sections["experience"].append(line)

        # ---------- SCORING ----------
        score = 20  # base for PDF presence

        if sections["headline"]:
            score += 10
        if sections["skills"]:
            score += min(25, len(sections["skills"]) * 3)
        if sections["certifications"]:
            score += 15
        if sections["education"]:
            score += 15
        if sections["experience"]:
            score += 15

        score = min(100, score)

        # ---------- FLAGS & MISSING ----------
        flags = []
        missing = []

        if not sections["experience"]:
            flags.append("No experience timeline detected")
            missing.append("Experience")

        if len(sections["skills"]) < 3:
            flags.append("Low skills density")
            missing.append("Skills depth")

        if not sections["certifications"]:
            missing.append("Certifications")

        return {
            "mode": "pdf_full",
            "linkedin_score": score,
            "sections": sections,
            "missing_sections": missing,
            "flags": flags
        }
