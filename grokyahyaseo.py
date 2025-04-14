import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import Counter
import re
from typing import Dict, List, Optional
import logging
import time
import io
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import nltk
from nltk.corpus import stopwords

# Download NLTK stopwords
nltk.download('stopwords')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SEOTool:
    def __init__(self, url: str, api_key: Optional[str] = None, strategy: str = 'desktop'):
        self.url = url
        self.api_key = api_key
        self.strategy = strategy
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
            logging.info(f"Successfully fetched {self.url}")
            return True
        except requests.RequestException as e:
            logging.error(f"Failed to fetch {self.url}: {e}")
            return False

    def extract_meta_tags(self) -> Dict[str, str]:
        meta_data = {}
        if not self.soup:
            return meta_data
        title_tag = self.soup.find('title')
        meta_data['title'] = title_tag.text.strip() if title_tag else 'No title found'
        meta_desc = self.soup.find('meta', attrs={'name': re.compile('description', re.I)})
        meta_data['description'] = meta_desc['content'].strip() if meta_desc and 'content' in meta_desc.attrs else 'No description found'
        meta_keywords = self.soup.find('meta', attrs={'name': re.compile('keywords', re.I)})
        meta_data['keywords'] = meta_keywords['content'].strip() if meta_keywords and 'content' in meta_keywords.attrs else 'No keywords found'
        robots_tag = self.soup.find('meta', attrs={'name': 'robots'})
        meta_data['robots'] = robots_tag['content'] if robots_tag else 'No robots tag found'
        canonical_tag = self.soup.find('link', rel='canonical')
        meta_data['canonical'] = canonical_tag['href'] if canonical_tag else 'No canonical tag found'
        return meta_data

    def analyze_keyword_density(self, min_length: int = 3) -> Dict[str, float]:
        if not self.soup:
            return {}
        stop_words = set(stopwords.words('english'))
        text_elements = self.soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span'])
        text = ' '.join(element.get_text().lower() for element in text_elements)
        words = re.findall(r'\b\w+\b', text)
        words = [word for word in words if len(word) >= min_length and word.isalpha() and word not in stop_words]
        word_counts = Counter(words)
        total_words = len(words)
        keyword_density = {word: (count / total_words * 100) for word, count in word_counts.items() if total_words > 0}
        return dict(sorted(keyword_density.items(), key=lambda x: x[1], reverse=True)[:10])

    def check_broken_links(self) -> List[Dict[str, str]]:
        broken_links = []
        if not self.soup:
            return broken_links
        links = self.soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            full_url = urljoin(self.url, href)
            try:
                response = requests.head(full_url, headers=self.headers, timeout=5, allow_redirects=True)
                if response.status_code >= 400:
                    broken_links.append({'url': full_url, 'status': response.status_code})
            except requests.RequestException:
                broken_links.append({'url': full_url, 'status': 'Failed to connect'})
        return broken_links

    def audit_on_page_seo(self) -> Dict[str, str]:
        audit_results = {}
        if not self.soup:
            return audit_results
        h1_tags = self.soup.find_all('h1')
        audit_results['h1_status'] = f"Found {len(h1_tags)} H1 tags" if h1_tags else "No H1 tag found"
        images = self.soup.find_all('img')
        missing_alt = [img for img in images if not img.get('alt')]
        audit_results['image_alt_status'] = f"{len(missing_alt)} images missing alt text" if missing_alt else "All images have alt text"
        meta_desc = self.extract_meta_tags().get('description', '')
        desc_length = len(meta_desc) if meta_desc != 'No description found' else 0
        audit_results['meta_description_length'] = f"Description length: {desc_length} (Ideal: 120-160)" if desc_length else "No meta description"
        return audit_results

    def analyze_content_length(self) -> Dict[str, any]:
        if not self.soup:
            return {'word_count': 0}
        text_elements = self.soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        text = ' '.join(element.get_text() for element in text_elements)
        words = re.findall(r'\b\w+\b', text)
        return {'word_count': len(words)}

    def analyze_internal_links(self) -> Dict[str, any]:
        if not self.soup:
            return {'internal_link_count': 0}
        base_domain = re.match(r'https?://[^/]+', self.url).group(0)
        links = self.soup.find_all('a', href=True)
        internal_links = [link['href'] for link in links if link['href'].startswith(base_domain) or link['href'].startswith('/')]
        return {'internal_link_count': len(internal_links)}

    def check_page_speed(self) -> Dict[str, any]:
        speed_data = {'response_time': self.response_time if self.response_time else 0.0}
        if self.api_key:
            try:
                service = build('pagespeedonline', 'v5', developerKey=self.api_key)
                result = service.pagespeedapi().runpagespeed(url=self.url, strategy=self.strategy).execute()
                lighthouse = result['lighthouseResult']
                speed_data['performance_score'] = lighthouse['categories']['performance']['score'] * 100
                speed_data['recommendations'] = [
                    audit['title'] for audit in lighthouse['audits'].values()
                    if 'title' in audit and audit.get('score', 1) < 0.9
                ][:3]
            except HttpError as e:
                logging.error(f"PageSpeed API error: {e}")
                speed_data['error'] = "Failed to fetch PageSpeed data—check your API key."
        return speed_data

    def run_seo_analysis(self) -> Dict[str, any]:
        if not self.fetch_page():
            return {'error': 'Failed to fetch page'}
        return {
            'meta_tags': self.extract_meta_tags(),
            'keyword_density': self.analyze_keyword_density(),
            'broken_links': self.check_broken_links(),
            'on_page_audit': self.audit_on_page_seo(),
            'content_length': self.analyze_content_length(),
            'internal_links': self.analyze_internal_links(),
            'page_speed': self.check_page_speed()
        }
