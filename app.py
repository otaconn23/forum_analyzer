import streamlit as st
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
import re
from time import time
from datetime import timedelta
from urllib.parse import urlparse, urlunparse

# Load OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Constants for async fetching and AI processing
HEADERS = {"User-Agent": "Mozilla/5.0"}
SEMAPHORE_LIMIT = 100
CHUNK_SIZE = 50

# Utility: Time formatting
def format_time(seconds):
    return str(timedelta(seconds=round(seconds)))[2:]  # Strip hours if 0

def clean_url(url):
    """Trim query parameters (? and beyond) from the URL."""
    parsed_url = urlparse(url)
    return urlunparse(parsed_url._replace(query=""))

# Asynchronous web fetching
async def fetch_page(session, url):
    """Fetch a single page with retries."""
    for attempt in range(3):
        try:
            async with session.get(url, headers=HEADERS, timeout=10) as response:
                return await response.text()
        except Exception:
            if attempt == 2:
                return None  # Return None after max retries
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

async def get_max_pages(base_url):
    """Fetch maximum page number from the forum."""
    async with aiohttp.ClientSession() as session:
        page_content = await fetch_page(session, base_url)
        if not page_content:
            return 1
        soup = BeautifulSoup(page_content, "lxml")
        page_links = soup.find_all("a", href=True, string=re.compile(r"\d+$"))
        return max((int(link.get_text(strip=True)) for link in page_links if link.get_text(strip=True).isdigit()), default=1)

async def scrape_pages(base_url, total_pages):
    """Scrape pages concurrently."""
    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
        async def scrape_single_page(page_num):
            url = f"{base_url}/{page_num}"
            async with semaphore:
                content = await fetch_page(session, url)
                return page_num, content
        tasks = [scrape_single_page(i) for i in range(1, total_pages + 1)]
        return await asyncio.gather(*tasks)

def parse_posts(page_content, base_url):
    """Extract posts from a single page."""
    if not page_content:
        return []
    soup = BeautifulSoup(page_content, "lxml")
    parsed = []
    for post in soup.find_all("section", class_="post_body"):
        content = post.find("div", class_="content")
        date = post.find("time")
        number = post.find("a", class_="anchor")
        parsed.append({
            "number": number.get_text(strip=True) if number else "N/A",
            "date": date.get("datetime") if date else "Unknown",
            "content": content.get_text(strip=True) if content else "No content",
            "url": f"{base_url}#{number.get_text(strip=True)}" if number else base_url
        })
    return parsed

def ai_request(prompt, model):
    """Reusable AI interaction function."""
    messages = [
        {"role": "system", "content": "You are a deal analysis expert."},
        {"role": "user", "content": prompt}
    ]
    response = openai.ChatCompletion.create(model=model, messages=messages)
    return response['choices'][0]['message']['content'].strip()

def analyze_posts(posts, model):
    """Analyze scraped posts with OpenAI."""
    chunks = ["\n".join(f"[{p['number']} | {p['date']}] {p['content']}" for p in posts[i:i + CHUNK_SIZE]) for i in range(0, len(posts), CHUNK_SIZE)]
    insights = []
    for chunk in chunks:
        prompt = (
            "Analyze the following forum posts. Extract:\n"
            "1. Deals, navigation paths, and fringe benefits (with post numbers).\n"
            "2. The best deal and relevant risks.\n\n"
            f"{chunk}"
        )
        insights.append(ai_request(prompt, model))
    return "\n\n".join(insights)

# Streamlit UI
st.title("Forum Analyzer")

# Input for forum URL with 'Paste' and 'Go' buttons
url_input = st.text_input("Enter URL:", key="url_input", help="Paste the URL of the forum thread you want to analyze.")

# Input for pages to scrape and model selection, both on the same line
col1, col2 = st.columns([1, 1])  # Set columns to be equal width
with col1:
    pages_input = st.text_input(
        "Pages to scrape:", 
        "All", 
        help="Number of pages to scrape. Type 'All' for all pages. You can enter a specific number (e.g., 10) or leave it blank for 'All'."
    )
with col2:
    model_choice = st.selectbox(
        "Choose a model:", 
        ["gpt-4", "gpt-3.5-turbo"], 
        help="Choose the model for analysis. GPT-4 provides better accuracy but is slower, while GPT-3.5 is faster and more efficient."
    )

# Main scraping and analysis logic
if url_input and st.button("Start"):
    with st.spinner("Processing..."):
        try:
            url = clean_url(url_input)  # Clean the URL
            pages_to_scrape = int(pages_input) if pages_input != "All" else asyncio.run(get_max_pages(url))
            scraped_pages = asyncio.run(scrape_pages(url, pages_to_scrape))
            posts = [post for _, content in scraped_pages for post in parse_posts(content, url)]
            st.write(f"Processed {len(posts)} posts from {pages_to_scrape} pages.")
            st.subheader("Analysis Summary")
            st.write(analyze_posts(posts, model_choice))
        except Exception as e:
            st.error(f"An error occurred: {e}")
