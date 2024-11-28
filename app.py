import streamlit as st
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
import re
from time import time
from datetime import timedelta
from urllib.parse import urlparse, urlunparse

# Global constants
openai.api_key = st.secrets["OPENAI_API_KEY"]
HEADERS = {"User-Agent": "Mozilla/5.0"}
SEMAPHORE_LIMIT = 100
CHUNK_SIZE = 50

# Default selectors (can be modified based on the website structure)
DEFAULT_SELECTORS = {
    "pagination_selector": "a.page-numbers",
    "post_selector": ".forum-post",
    "content_selector": ".post-content",
    "date_selector": ".post-date",
    "post_number_selector": ".post-number",
}

# Utility: Time formatting
def format_time(seconds):
    return str(timedelta(seconds=round(seconds)))

def clean_url(url):
    """Trim query parameters (? and beyond) from the URL."""
    parsed_url = urlparse(url)
    return urlunparse(parsed_url._replace(query=""))

# Asynchronous web fetching
async def fetch_page(session, url):
    async with session.get(url, headers=HEADERS, timeout=10) as response:
        return await response.text()

async def get_max_pages(base_url, selectors):
    """Fetch maximum page number from the forum."""
    async with aiohttp.ClientSession() as session:
        page_content = await fetch_page(session, base_url)
        if not page_content:
            return 1
        soup = BeautifulSoup(page_content, "lxml")
        page_links = soup.select(selectors["pagination_selector"])
        return max((int(link.get_text(strip=True)) for link in page_links if link.get_text(strip=True).isdigit()), default=1)

async def scrape_forum_pages(base_url, pages_to_scrape, selectors):
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    async with aiohttp.ClientSession() as session:
        tasks = [
            scrape_page(session, i, base_url, semaphore, selectors)
            for i in range(1, pages_to_scrape + 1)
        ]
        results = []
        for i, task in enumerate(asyncio.as_completed(tasks), start=1):
            page_data = await task
            results.append(page_data)
            st.progress(i / pages_to_scrape)  # Update Streamlit progress bar
        return results

async def scrape_page(session, page_num, base_url, semaphore, selectors):
    async with semaphore:
        page_url = f"{base_url}/{page_num}"
        content = await fetch_page(session, page_url)
        return page_num, content

def parse_posts(page_content, base_url, selectors):
    """Extract posts using the given selectors."""
    if not page_content:
        return []
    soup = BeautifulSoup(page_content, "lxml")
    parsed = []
    for post in soup.select(selectors["post_selector"]):
        content = post.select_one(selectors["content_selector"])
        date = post.select_one(selectors["date_selector"])
        number = post.select_one(selectors["post_number_selector"])
        parsed.append({
            "number": number.get_text(strip=True) if number else "N/A",
            "date": date.get("datetime") if date else "Unknown",
            "content": content.get_text(strip=True) if content else "No content",
            "url": f"{base_url}#{number.get_text(strip=True)}" if number else base_url
        })
    return parsed

def ai_request(prompt, model):
    messages = [
        {"role": "system", "content": "You are a deal analysis expert."},
        {"role": "user", "content": prompt}
    ]
    response = openai.ChatCompletion.create(model=model, messages=messages)
    return response['choices'][0]['message']['content'].strip()

def analyze_posts(posts, model):
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

# Collect forum URL and selectors from user
url_input = st.text_input("Enter URL:", help="Paste the URL of the forum thread to analyze.")
selectors = {
    "pagination_selector": st.text_input("Pagination Selector:", DEFAULT_SELECTORS["pagination_selector"]),
    "post_selector": st.text_input("Post Selector:", DEFAULT_SELECTORS["post_selector"]),
    "content_selector": st.text_input("Content Selector:", DEFAULT_SELECTORS["content_selector"]),
    "date_selector": st.text_input("Date Selector:", DEFAULT_SELECTORS["date_selector"]),
    "post_number_selector": st.text_input("Post Number Selector:", DEFAULT_SELECTORS["post_number_selector"]),
}

col1, col2 = st.columns(2)
with col1:
    pages_input = st.text_input("Pages to scrape:", "All", help="Type 'All' or specify a number (e.g., 10).")
with col2:
    model_choice = st.selectbox("AI Model:", ["gpt-4", "gpt-3.5-turbo"])

if url_input and st.button("Start"):
    try:
        url = clean_url(url_input)
        pages_to_scrape = int(pages_input) if pages_input != "All" else asyncio.run(get_max_pages(url, selectors))
        scraped_pages = asyncio.run(scrape_forum_pages(url, pages_to_scrape, selectors))
        posts = [post for _, content in scraped_pages for post in parse_posts(content, url, selectors)]
        st.write(f"Processed {len(posts)} posts from {pages_to_scrape} pages.")
        st.subheader("Analysis Summary")
        st.write(analyze_posts(posts, model_choice))
    except Exception as e:
        st.error(f"Error: {e}")
