import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import Counter
import re
from typing import Dict, List, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SEOTool:
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url
        self.api_key = api_key
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.soup = None
        self.content = None

    def fetch_page(self) -> bool:
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
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
        return meta_data

    def analyze_keyword_density(self, min_length: int = 3) -> Dict[str, float]:
        if not self.soup:
            return {}
        text_elements = self.soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span'])
        text = ' '.join(element.get_text().lower() for element in text_elements)
        words = re.findall(r'\b\w+\b', text)
        words = [word for word in words if len(word) >= min_length and word.isalpha()]
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

    def run_seo_analysis(self) -> Dict[str, any]:
        if not self.fetch_page():
            return {'error': 'Failed to fetch page'}
        return {
            'meta_tags': self.extract_meta_tags(),
            'keyword_density': self.analyze_keyword_density(),
            'broken_links': self.check_broken_links(),
            'on_page_audit': self.audit_on_page_seo()
        }

def generate_seo_recommendations(results: Dict[str, any]) -> List[str]:
    """Generate SEO recommendations based on analysis results."""
    recommendations = []

    # Meta Tags Recommendations
    meta_tags = results['meta_tags']
    if meta_tags['title'] == 'No title found':
        recommendations.append("Add a unique title tag (50-60 characters) with primary keywords.")
    elif len(meta_tags['title']) > 60:
        recommendations.append("Shorten the title tag to 50-60 characters for optimal SEO.")
    if meta_tags['description'] == 'No description found':
        recommendations.append("Add a meta description (120-160 characters) with a call-to-action.")
    elif not (120 <= len(meta_tags['description']) <= 160):
        recommendations.append("Adjust meta description to 120-160 characters for best results.")
    if meta_tags['keywords'] == 'No keywords found':
        recommendations.append("Add a meta keywords tag with 5-10 relevant terms (e.g., 'translation, localization').")

    # Keyword Density Recommendations
    keyword_density = results['keyword_density']
    top_keywords = list(keyword_density.keys())
    if top_keywords and all(kw in ['the', 'and', 'for', 'to', 'of'] for kw in top_keywords[:3]):
        recommendations.append("Optimize content with specific keywords relevant to your topic (aim for 2-3% density).")
    else:
        recommendations.append("Ensure primary keywords appear naturally in content (2-3% density) and in headings.")

    # Broken Links Recommendations
    broken_links = results['broken_links']
    if broken_links:
        for link in broken_links:
            recommendations.append(f"Fix broken link: {link['url']} (Status: {link['status']}).")
    else:
        recommendations.append("No broken links found—great job! Consider adding internal links to related pages.")

    # On-Page SEO Recommendations
    on_page_audit = results['on_page_audit']
    h1_count = int(on_page_audit['h1_status'].split()[1]) if 'Found' in on_page_audit['h1_status'] else 0
    if h1_count == 0:
        recommendations.append("Add one H1 tag with your primary keyword.")
    elif h1_count > 1:
        recommendations.append("Reduce to one H1 tag per page for SEO best practices.")
    missing_alt_count = int(on_page_audit['image_alt_status'].split()[0]) if 'missing' in on_page_audit['image_alt_status'] else 0
    if missing_alt_count > 0:
        recommendations.append(f"Add descriptive alt text to {missing_alt_count} images using relevant keywords.")
    if 'No meta description' in on_page_audit['meta_description_length']:
        recommendations.append("Add a meta description (120-160 characters) to improve click-through rates.")

    # General Recommendations
    recommendations.append("Check page load speed with Google PageSpeed Insights and optimize if needed.")
    recommendations.append("Ensure the page is mobile-friendly (test with Google’s Mobile-Friendly Test).")
    recommendations.append("Add internal links to related pages and seek quality backlinks.")

    return recommendations

# Streamlit Interface
def main():
    st.title("Grok SEO Analysis Tool")
    st.write("Enter a URL to perform an SEO audit and get optimization recommendations.")

    # Input URL
    url = st.text_input("Website URL", "https://example.com")
    analyze_button = st.button("Analyze")

    if analyze_button and url:
        with st.spinner("Analyzing..."):
            seo_tool = SEOTool(url)
            results = seo_tool.run_seo_analysis()

            if 'error' in results:
                st.error(results['error'])
            else:
                # Display Meta Tags
                st.subheader("Meta Tags")
                for key, value in results['meta_tags'].items():
                    st.write(f"**{key.capitalize()}**: {value}")

                # Display Keyword Density
                st.subheader("Top 10 Keywords (Density %)")
                for keyword, density in results['keyword_density'].items():
                    st.write(f"{keyword}: {density:.2f}%")

                # Display Broken Links
                st.subheader("Broken Links")
                if results['broken_links']:
                    for link in results['broken_links']:
                        st.write(f"URL: {link['url']} - Status: {link['status']}")
                else:
                    st.success("No broken links found!")

                # Display On-Page SEO Audit
                st.subheader("On-Page SEO Audit")
                for key, value in results['on_page_audit'].items():
                    st.write(f"**{key.replace('_', ' ').capitalize()}**: {value}")

                # Display SEO Recommendations
                st.subheader("SEO Recommendations")
                recommendations = generate_seo_recommendations(results)
                for rec in recommendations:
                    st.write(f"- {rec}")

if __name__ == "__main__":
    main()
