import streamlit as st
import requests
import aiohttp
import asyncio
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

# Conditional NLTK stopwords import
try:
    from nltk.corpus import stopwords
except LookupError:
    nltk.download('stopwords')
    from nltk.corpus import stopwords

# Logging setup
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
        self.page_text = None  # Cache for text content

    def fetch_page(self) -> bool:
        try:
            start_time = time.time()
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            self.response_time = time.time() - start_time
            self.content = response.text
            self.soup = BeautifulSoup(self.content, 'html.parser')
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
            logging.warning("No page content for keyword analysis")
            return {}
        if not self.page_text:
            text_elements = self.soup.find_all(['p', 'h1', 'h2', 'h3', 'span'])
            self.page_text = ' '.join(el.get_text().lower() for el in text_elements if el.get_text()) or ""
            logging.info(f"Extracted {len(self.page_text)} chars for keyword analysis")
        if not self.page_text:
            logging.warning("No text content for keyword analysis")
            return {}
        stop_words = set(stopwords.words('english'))
        words = re.findall(r'\b\w+\b', self.page_text)
        words = [w for w in words if len(w) >= min_length and w not in stop_words]
        count = Counter(words)
        total = sum(count.values())
        return {k: (v / total * 100) for k, v in count.most_common(10)} if total else {}

    async def _check_link(self, session, href: str) -> Dict[str, str]:
        try:
            async with session.head(href, timeout=5, allow_redirects=True) as r:
                if r.status >= 400:
                    return {'url': href, 'status': str(r.status)}
                return None
        except:
            return {'url': href, 'status': 'Failed'}

    async def check_broken_links(self) -> List[Dict[str, str]]:
        if not self.soup:
            return []
        broken = []
        links = self.soup.find_all('a', href=True)[:10]  # Limit to 10 links
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [self._check_link(session, urljoin(self.url, link['href'])) for link in links]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            broken = [r for r in results if r is not None]
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
            logging.warning("No page content for content length analysis")
            return {'word_count': 0}
        if not self.page_text:
            tags = self.soup.find_all(['p', 'h1', 'h2', 'h3'])
            self.page_text = ' '.join(t.get_text() for t in tags if t.get_text()) or ""
            logging.info(f"Extracted {len(self.page_text)} chars for content length")
        if not self.page_text:
            logging.warning("No text content for content length")
            return {'word_count': 0}
        words = re.findall(r'\b\w+\b', self.page_text)
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

    async def run_seo_analysis(self) -> Dict[str, any]:
        if not self.fetch_page():
            return {'error': 'Failed to fetch the page.'}
        # Run async broken links check
        broken_links = await self.check_broken_links()
        return {
            'meta_tags': self.extract_meta_tags(),
            'keyword_density': self.analyze_keyword_density(),
            'broken_links': broken_links,
            'on_page_audit': self.audit_on_page_seo(),
            'content_length': self.analyze_content_length(),
            'internal_links': self.analyze_internal_links(),
            'page_speed': self.check_page_speed()
        }

# -------------------- STREAMLIT UI -------------------------

def generate_todo_list(result):
    todos = []
    meta = result['meta_tags']
    audit = result['on_page_audit']
    word_count = result['content_length']['word_count']
    speed = result['page_speed']

    if meta['keywords'] == 'No keywords found':
        todos.append("➕ Add a meta keywords tag (optional).")

    if 'No H1' in audit['h1_status']:
        todos.append("❌ Add at least one H1 tag with a primary keyword.")
    elif 'Found' in audit['h1_status']:
        h1_count = int(audit['h1_status'].split()[1])
        if h1_count > 1:
            todos.append("⚠️ Reduce H1 tags to only one.")

    if 'missing alt' in audit['image_alt_status']:
        todos.append("🖼️ Add alt text to all images for accessibility and SEO.")

    if word_count < 300:
        todos.append("✍️ Add more content — aim for at least 800 words.")

    if result['broken_links']:
        todos.append("🔗 Fix broken or redirected external/internal links.")

    if 'performance_score' in speed:
        if speed['performance_score'] < 90:
            todos.append("🚀 Improve PageSpeed score — optimize images & scripts.")
    else:
        if speed['response_time'] > 2.0:
            todos.append("⚠️ Page load time is slow — reduce to under 2s.")

    return todos

def main():
    st.set_page_config(page_title='SEO Analyzer', layout='wide')
    st.title("🔍 SEO Audit Tool")
    url = st.text_input("Enter URL:", "https://example.com")
    api_key = st.text_input("Google PageSpeed API Key (optional):", type='password')
    strategy = st.selectbox("Choose PageSpeed Strategy", ["desktop", "mobile"])
    run_pagespeed = st.checkbox("Run PageSpeed Analysis (slower)", value=False)

    if st.button("Run SEO Audit") and url:
        tool = SEOTool(url, api_key=api_key if run_pagespeed else None, strategy=strategy)
        with st.spinner("Analyzing..."):
            # Progress bar
            progress_bar = st.progress(0)
            progress_steps = 7  # Number of analysis steps
            progress = 0

            # Run async analysis
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(tool.run_seo_analysis())
            progress += 1
            progress_bar.progress(progress / progress_steps)

            if 'error' in result:
                st.error(result['error'])
                return

            # Display results
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Meta Tags")
                st.json(result['meta_tags'])
            progress += 1
            progress_bar.progress(progress / progress_steps)

            with col2:
                st.subheader("On-Page SEO")
                st.json(result['on_page_audit'])
            progress += 1
            progress_bar.progress(progress / progress_steps)

            with st.expander("Top Keywords"):
                st.write(result['keyword_density'])
            progress += 1
            progress_bar.progress(progress / progress_steps)

            with st.expander("Broken Links"):
                if result['broken_links']:
                    for link in result['broken_links']:
                        st.markdown(f"- 🔗 `{link['url']}` — ❌ Status: {link['status']}")
                else:
                    st.success("No broken links found.")
            progress += 1
            progress_bar.progress(progress / progress_steps)

            st.subheader("Content & Internal Links")
            st.write(f"📄 Word Count: **{result['content_length']['word_count']}**")
            st.write(f"🔗 Internal Links: **{result['internal_links']['internal_link_count']}**")
            progress += 1
            progress_bar.progress(progress / progress_steps)

            st.subheader("Page Speed")
            st.write(f"⏱️ Response Time: {result['page_speed']['response_time']} seconds")
            if 'performance_score' in result['page_speed']:
                score = result['page_speed']['performance_score']
                st.metric("PageSpeed Score", f"{score}/100")
                st.progress(int(score))
                if result['page_speed'].get('recommendations'):
                    st.write("Optimization Suggestions:")
                    for tip in result['page_speed']['recommendations']:
                        st.markdown(f"- ⚡ {tip}")
            elif 'error' in result['page_speed']:
                st.error(result['page_speed']['error'])
            progress += 1
            progress_bar.progress(progress / progress_steps)

            st.subheader("📋 SEO To-Do List")
            todo_list = generate_todo_list(result)
            if todo_list:
                for task in todo_list:
                    st.markdown(f"- {task}")
            else:
                st.success("Your page is in excellent SEO shape! ✅")

            # Export results
            st.subheader("Export Results")
            export_data = {
                'Meta Tags': [f"{k}: {v}" for k, v in result['meta_tags'].items()],
                'Keyword Density': [f"{k}: {v:.2f}%" for k, v in result['keyword_density'].items()],
                'Broken Links': [f"{link['url']} (Status: {link['status']})" for link in result['broken_links']] or ['None'],
                'On-Page SEO': [f"{k}: {v}" for k, v in result['on_page_audit'].items()],
                'Content Length': [f"Word Count: {result['content_length']['word_count']}"],
                'Internal Links': [f"Count: {result['internal_links']['internal_link_count']}"],
                'Page Speed': [f"Response Time: {result['page_speed']['response_time']}s"] + ([f"Score: {result['page_speed']['performance_score']}/100"] if 'performance_score' in result['page_speed'] else []),
                'To-Do List': todo_list
            }
            df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in export_data.items()]))
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download as CSV",
                data=csv,
                file_name=f"seo_analysis_{url.split('//')[1].replace('/', '_')}.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
