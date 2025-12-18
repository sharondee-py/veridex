# VeriDex — Candidate Intelligence Platform

VeriDex is a Python-based backend system that analyses developer profiles by ingesting data from GitHub repositories, portfolio websites, and uploaded LinkedIn PDFs. The platform evaluates code structure, architectural signals, and professional visibility to produce explainable credibility insights.

## Features
- GitHub repository analysis and code intelligence
- Heuristic scoring of project depth and engineering maturity
- LinkedIn PDF parsing and profile completeness evaluation
- Portfolio signal analysis
- RESTful backend architecture

## Tech Stack
- Python
- Flask
- REST APIs
- GitHub API
- Requests / BeautifulSoup
- PDF parsing (pypdf)

## Architecture Overview
The system is structured around modular analysis engines responsible for ingesting, processing, and scoring different data sources. Each engine operates independently and contributes to a final aggregated credibility score.

## Why VeriDex
VeriDex was built to demonstrate backend system design, data ingestion pipelines, API integration, and explainable scoring logic rather than UI-focused development.

## Getting Started

```bash
git clone https://github.com/sharondee-py/veridex.git
cd veridex
pip install -r requirements.txt
python app.py
