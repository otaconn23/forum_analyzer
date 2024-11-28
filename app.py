import streamlit as st
import aiohttp
import asyncio
import openai
from bs4 import BeautifulSoup
import json
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
    """Fetch a single page asynchronously with retry logic."""
    async with semaphore:
        for attempt in range(3):  # Retry up to 3 times
            try:
                async with session.get(url, headers=HEADERS, timeout=10) as response:
                    return await response.text()
            except Exception as e:
                if attempt == 2:
                    return f"Error: {e}"
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

async def scrape_forum_pages(base_url, pages_to_scrape):
    """Scrape forum pages asynchronously."""
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_page(session, f"{base_url}/{i}")
            for i in range(1, pages_to_scrape + 1)
        ]
        return await asyncio.gather(*tasks)

def parse_posts(page_content, base_url):
    """Parses forum posts from page content."""
    soup = BeautifulSoup(page_content, "lxml")
    parsed_posts = []

    posts = soup.select("section.post_body")  # Adjust selector as per forum structure
    for post in posts:
        content_div = post.select_one("div.content")  # Adjust selector as per forum structure
        date_div = post.select_one("time")  # Adjust selector as per forum structure
        post_div = post.select_one("a.anchor")  # Adjust selector as per forum structure

        parsed_posts.append({
            "number": post_div.get_text(strip=True) if post_div else "N/A",
            "date": date_div.get("datetime") if date_div else "Unknown",
            "content": content_div.get_text(strip=True) if content_div else "No content",
            "url": f"{base_url}#{post_div.get_text(strip=True)}" if post_div else base_url
        })

    return parsed_posts

def ai_request(prompt, model):
    """Reusable AI interaction function."""
    messages = [
        {"role": "system", "content": "You are a deal analysis expert."},
        {"role": "user", "content": prompt}
    ]
    response = openai.ChatCompletion.create(model=model, messages=messages)
    return response['choices'][0]['message']['content'].strip()

def analyze_posts(posts, model):
    """Analyze posts using OpenAI API with post number citations."""
    chunk_size = 50
    chunks = ["\n".join([f"[{p['number']} | {p['date']}] {p['content']}" for p in posts[i:i + chunk_size]]) for i in range(0, len(posts), chunk_size)]
    insights = []

    for chunk in chunks:
        messages = [
            {"role": "system", "content": "You are a deal analysis expert summarizing forum discussions."},
            {"role": "user", "content": (
                "Analyze the following forum posts related to a deal thread. Extract only the critical information:\n"
                "1. Specific deals or unique offers with post numbers.\n"
                "2. Navigation paths (departments contacted, codes used) with post numbers.\n"
                "3. Fringe deals or extras received, with post numbers.\n"
                "4. Evaluate multiple deal options and suggest the best value.\n"
                "5. Identify risks or drawbacks.\n\n"
                f"{chunk}"
            )}
        ]
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages
        )
        insights.append(response['choices'][0]['message']['content'].strip())

    return "\n\n".join(insights)

# Streamlit UI
st.title("Forum Analyzer")

# URL Input Box and Pages to Scrape
col1, col2 = st.columns([1, 1])  # Set columns to be equal width
with col1:
    url_input = st.text_input("Enter URL:", key="url_input", placeholder="Paste URL here", help="Enter or paste the URL of the forum thread you want to analyze.")
with col2:
    pages_input = st.text_input("Pages to scrape:", "All", help="Number of pages to scrape. Type 'All' for all pages. Enter a number for specific pages.")

model_choice = st.selectbox(
    "Choose a model:",
    ["gpt-4", "gpt-3.5-turbo"],
    help="GPT-4 is more accurate, while GPT-3.5 is faster."
)

# Main scraping and analysis logic
if url_input and st.button("Start"):
    with st.spinner("Processing..."):
        try:
            url = clean_url(url_input)  # Clean the URL
            pages_to_scrape = int(pages_input) if pages_input != "All" else asyncio.run(get_max_pages(url))
            scraped_pages = asyncio.run(scrape_forum_pages(url, pages_to_scrape))
            posts = [post for _, content in scraped_pages for post in parse_posts(content, url)]
            st.write(f"Processed {len(posts)} posts from {pages_to_scrape} pages.")
            st.subheader("Analysis Summary")
            st.write(analyze_posts(posts, model_choice))
        except Exception as e:
            st.error(f"An error occurred: {e}")
