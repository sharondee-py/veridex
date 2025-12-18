from flask import Flask, render_template, request, jsonify, send_file
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from engines.github_engine import GitHubEngine
from engines.linkedin_engine import LinkedInEngine

app = Flask(__name__)

def valid_github(url):
    return re.match(r"^https?://(www\.)?github\.com/.+", url)

def valid_linkedin(url):
    return re.match(r"^https?://(www\.)?linkedin\.com/in/.+", url)

def valid_url(url):
    return re.match(r"^https?://.+", url)

@app.route("/", methods=["GET", "POST"])
def index():
    error = None

    if request.method == "POST":
        github = request.form.get("github")
        linkedin = request.form.get("linkedin")
        portfolio = request.form.get("portfolio")

        linkedin_pdf = request.files.get("linkedin_pdf")
        linkedin_pdf_bytes = linkedin_pdf.read() if linkedin_pdf and linkedin_pdf.filename else None

        if not github or not valid_github(github):
            error = "Invalid GitHub URL"
        elif linkedin and not valid_linkedin(linkedin):
            error = "Invalid LinkedIn URL"
        elif portfolio and not valid_url(portfolio):
            error = "Invalid Portfolio URL"
        else:
            try:
                github_scanner = GitHubEngine(github, portfolio_url=portfolio)
                github_report = github_scanner.analyze()
            except Exception as e:
                return jsonify({"error": f"GitHub Scan Failed: {str(e)}"})

            # LinkedIn: prefer PDF if provided
            linkedin_report = None
            if linkedin_pdf_bytes:
                linkedin_report = LinkedInEngine(pdf_bytes=linkedin_pdf_bytes).analyze()
            elif linkedin:
                linkedin_report = LinkedInEngine(linkedin_url=linkedin).analyze()

            return jsonify({
                "github": github_report,
                "linkedin": linkedin_report,
                "portfolio": github_report.get("portfolio", {})
            })

    return render_template("index.html", error=error)

@app.route("/report", methods=["POST"])
def report():
    data = request.get_json() or {}
    github = data.get("github", {})
    linkedin = data.get("linkedin", {}) or {}
    portfolio = data.get("portfolio", {}) or {}

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40

    def line(text, size=11, dy=14, bold=False):
        nonlocal y
        if y < 60:
            c.showPage()
            y = height - 40
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(40, y, str(text)[:120])
        y -= dy

    line("VeriDex V2 Candidate Report", size=16, dy=24, bold=True)
    line("----------------------------------------", dy=18)

    line(f"GitHub Username: {github.get('username', 'N/A')}", bold=True)
    line(f"Overall Credibility: {github.get('credibility_score', 0)}/100")
    line(f"Dev Maturity: {github.get('dev_maturity', 'N/A')}", dy=18)

    line("Summary:", bold=True, dy=16)
    summary = github.get("summary", "")
    for chunk in re.findall(r".{1,95}(?:\s+|$)", summary):
        line(chunk.strip())

    line("", dy=16)
    line("Top Repositories:", bold=True, dy=16)
    repos = github.get("code_intel", {}).get("repos", []) if isinstance(github.get("code_intel", {}), dict) else []
    top = sorted(repos, key=lambda r: r.get("depth_score", 0), reverse=True)[:3]
    for rinfo in top:
        line(f"- {rinfo.get('name','repo')} ({rinfo.get('dominant_language','?')}): {rinfo.get('depth_score',0)}/100")

    line("", dy=16)
    line("Portfolio:", bold=True, dy=16)
    line(f"Portfolio Score: {portfolio.get('portfolio_score', 'N/A')}/100")
    for f in portfolio.get("flags", []):
        line(f"- {f}")

    line("", dy=16)
    line("LinkedIn:", bold=True, dy=16)
    if linkedin:
        if "error" in linkedin:
            line(f"LinkedIn: {linkedin.get('error')}")
            line(f"Hint: {linkedin.get('hint','')}")
        else:
            line(f"LinkedIn Mode: {linkedin.get('mode','N/A')}")
            line(f"LinkedIn Score: {linkedin.get('linkedin_score','N/A')}")
            for f in linkedin.get("flags", []):
                line(f"- {f}")
    else:
        line("No LinkedIn provided")

    c.showPage()
    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="veridex-v2-report.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
