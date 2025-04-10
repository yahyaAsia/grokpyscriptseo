# Grok SEO Analysis Tool

A Streamlit-based SEO tool that analyzes websites for meta tags, keyword density, broken links, page speed, and more.

## Features
- Extracts meta tags (title, description, keywords)
- Analyzes keyword density
- Checks for broken links (up to 10)
- Audits on-page SEO elements (H1, alt text)
- Measures content length and internal links
- Optional PageSpeed Insights analysis
- Exports results as CSV

## How to Use
1. Enter a website URL (e.g., `https://example.com`).
2. Optionally provide a Google PageSpeed API key (e.g., `AIzaSyC_wiEhnXkOTLf8RCTCcv8gIOVQgRLakGs`).
3. Check "Run PageSpeed Analysis" if desired (note: adds extra time).
4. Click "Analyze" and review the results.

## Setup Locally
```bash
git clone https://github.com/yahyaAsia/grokpyscriptseo.git
cd grokpyscriptseo
pip install -r requirements.txt
streamlit run grokyahyaseo.py
