import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import Counter
import re
from typing import Dict, List, Optional
import logging
import time
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import nltk
from nltk.corpus import stopwords

# Download stopwords
nltk.download('stopwords')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SEOTool:
    def __init__(self, url: str, api_key: Optional[str] = None, strategy: str = 'desktop'):
        self.url = url
        self.api_key = api_key
        self.strategy = strategy
        self.headers = {'User-Agent': 'Mozilla/5.0'}
        self.soup = None
        self.content = None
        self.response_time = None

    def fetch_page(self) -> bool:
        try:
            start_time = time.time()
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            self.response_time = time.time() - start_time
            self.content = response.text
            self.soup = BeautifulSoup(self.content, 'html.parser')
            logging.info(f"Fetched {self.url} successfully")
            return True
        except requests.RequestException as e:
            logging.error(f"Error fetching {self.url}: {e}")
            return False

    def extract_meta_tags(self) -> Dict[str, str]:
        meta_data = {}
        if not self.soup:
            return meta_data
        title_tag = self.soup.find('title')
        meta_data['title'] = title_tag.text.strip() if title_tag else 'No title found'
        desc_tag = self.soup.find('meta', attrs={'name': re.compile('description', re.I)})
        meta_data['description'] = desc_tag['content'].strip() if desc_tag and 'content' in desc_tag.attrs else 'No description found'
        keywords_tag = self.soup.find('meta', attrs={'name': re.compile('keywords', re.I)})
        meta_data['keywords'] = keywords_tag['content'].strip() if keywords_tag and 'content' in keywords_tag.attrs else 'No keywords found'
        canonical = self.soup.find('link', rel='canonical')
        meta_data['canonical'] = canonical['href'] if canonical else 'No canonical tag found'
        robots_tag = self.soup.find('meta', attrs={'name': 'robots'})
        meta_data['robots'] = robots_tag['content'] if robots_tag else 'No robots tag found'
        return meta_data

    def analyze_keyword_density(self, min_length=3) -> Dict[str, float]:
        if not self.soup:
            return {}
        stop_words = set(stopwords.words('english'))
        text_elements = self.soup.find_all(['p', 'h1', 'h2', 'h3', 'span'])
        text = ' '.join(el.get_text().lower() for el in text_elements)
        words = re.findall(r'\\b\\w+\\b', text)
        words = [w for w in words if len(w) >= min_length and w not in stop_words]
        count = Counter(words)
        total = sum(count.values())
        return {k: (v / total * 100) for k, v in count.most_common(10)} if total else {}

    def check_broken_links(self) -> List[Dict[str, str]]:
        if not self.soup:
            return []
        broken = []
        links = self.soup.find_all('a', href=True)
        for link in links:
            href = urljoin(self.url, link['href'])
            try:
                r = requests.head(href, timeout=5, allow_redirects=True)
                if r.status_code >= 400:
                    broken.append({'url': href, 'status': str(r.status_code)})
            except:
                broken.append({'url': href, 'status': 'Failed'})
        return broken

    def audit_on_page_seo(self) -> Dict[str, str]:
        results = {}
        if not self.soup:
            return results
        h1s = self.soup.find_all('h1')
        results['h1_status'] = f"Found {len(h1s)} H1 tag(s)" if h1s else "No H1 tag found"
        imgs = self.soup.find_all('img')
        missing = sum(1 for img in imgs if not img.get('alt'))
        results['image_alt_status'] = f"{missing} images missing alt text" if missing else "All images have alt text"
        desc = self.extract_meta_tags().get('description', '')
        results['meta_description_length'] = f"Description length: {len(desc)}" if desc else "No meta description"
        return results

    def analyze_content_length(self) -> Dict[str, int]:
        if not self.soup:
            return {'word_count': 0}
        tags = self.soup.find_all(['p', 'h1', 'h2', 'h3'])
        text = ' '.join(t.get_text() for t in tags)
        words = re.findall(r'\\b\\w+\\b', text)
        return {'word_count': len(words)}

    def analyze_internal_links(self) -> Dict[str, int]:
        if not self.soup:
            return {'internal_link_count': 0}
        domain = re.match(r'https?://[^/]+', self.url).group(0)
        links = self.soup.find_all('a', href=True)
        internal = [l['href'] for l in links if l['href'].startswith('/') or l['href'].startswith(domain)]
        return {'internal_link_count': len(internal)}

    def check_page_speed(self) -> Dict[str, any]:
        data = {'response_time': round(self.response_time or 0, 2)}
        if self.api_key:
            try:
                service = build('pagespeedonline', 'v5', developerKey=self.api_key)
                result = service.pagespeedapi().runpagespeed(url=self.url, strategy=self.strategy).execute()
                score = result['lighthouseResult']['categories']['performance']['score'] * 100
                data['performance_score'] = score
                audits = result['lighthouseResult']['audits']
                tips = [v['title'] for v in audits.values() if 'title' in v and v.get('score', 1) < 0.9]
                data['recommendations'] = tips[:3]
            except HttpError as e:
                data['error'] = str(e)
        return data

    def run_seo_analysis(self) -> Dict[str, any]:
        if not self.fetch_page():
            return {'error': 'Failed to fetch the page.'}
        return {
            'meta_tags': self.extract_meta_tags(),
            'keyword_density': self.analyze_keyword_density(),
            'broken_links': self.check_broken_links(),
            'on_page_audit': self.audit_on_page_seo(),
            'content_length': self.analyze_content_length(),
            'internal_links': self.analyze_internal_links(),
            'page_speed': self.check_page_speed()
        }

# -------------------- STREAMLIT UI -------------------------

def main():
    st.set_page_config(page_title='SEO Analyzer', layout='wide')
    st.title(\"🔍 SEO Audit Tool\")
    url = st.text_input(\"Enter URL:\", \"https://example.com\")
    api_key = st.text_input(\"Google PageSpeed API Key (optional):\", type='password')
    strategy = st.selectbox(\"Choose PageSpeed Strategy\", [\"desktop\", \"mobile\"])

    if st.button(\"Run SEO Audit\") and url:
        tool = SEOTool(url, api_key=api_key, strategy=strategy)
        with st.spinner(\"Analyzing...\"):
            result = tool.run_seo_analysis()
        if 'error' in result:
            st.error(result['error'])
            return

        st.subheader(\"Meta Tags\")
        st.json(result['meta_tags'])

        st.subheader(\"Top Keywords\")
        st.write(result['keyword_density'])

        st.subheader(\"Broken Links\")
        if result['broken_links']:
            st.write(result['broken_links'])
        else:
            st.success(\"No broken links found.\")

        st.subheader(\"On-Page SEO Check\")
        st.json(result['on_page_audit'])

        st.subheader(\"Content Length\")
        st.write(f\"Word Count: {result['content_length']['word_count']}\")
        st.subheader(\"Internal Links\")
        st.write(f\"Internal Links: {result['internal_links']['internal_link_count']}\")
        st.subheader(\"Page Speed\")
        st.write(result['page_speed'])

if __name__ == '__main__':
    main()
