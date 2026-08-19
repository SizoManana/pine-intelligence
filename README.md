# PINE — Personal Intelligence Engine

A locally-hosted CRO and UI/UX audit tool that analyses any website in under 2 minutes.

Paste a URL → get a full consultant-style report covering visual design quality, 
code health, accessibility, trust signals, and conversion rate issues — cross-referenced 
and scored.

## How it works

1. Headless Chromium (Playwright) captures section-by-section screenshots
2. Claude Vision analyses each section against CRO and UX best practice
3. HTML/CSS is parsed independently — WCAG contrast calculated from scratch
4. Visual and code findings are cross-referenced to surface gaps and contradictions
5. A structured HTML report is generated with scores, priorities, and cited recommendations

## Setup

### Requirements
- Python 3.10+
- An Anthropic API key (get one at https://console.anthropic.com)

### Install

git clone https://github.com/SizoManana/pine-intelligence.git
cd pine-intelligence
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
playwright install chromium

### Configure

Create a .env file in the project root:
ANTHROPIC_API_KEY=your-api-key-here

### Run

python3 app.py

Open your browser at http://localhost:5000

## Cost

Each full analysis uses roughly 5–8 Claude API calls.
Approximate cost: $0.15–0.50 per analysis.

## Built with

- Python + Flask
- Playwright (headless Chromium)
- Anthropic Claude API (claude-sonnet-4-6)
- BeautifulSoup4 + tinycss2
- Pillow

## Author

Siphiwo Sizonqoba Manana
CRO & Product Designer
https://www.linkedin.com/in/siphiwo-sizonqoba-manana-8a19591ab/
