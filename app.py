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
        page_links = soup.find_all("a", href=True, string=re.compile(r"^\d+$"))
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
    for post in soup.find_all("div", class_="post_body"):  # Adjusted to find post body
        content = post.find("div", class_="content")
        date = post.find("time")
        number = post.find("span", class_="post_number")
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

# Input for forum URL with a subtle "Paste" button
col1, col2 = st.columns([5, 1])

with col1:
    url_input = st.text_input("Enter URL:")

with col2:
    paste_button = st.button("Paste", key="paste_button")

# URL paste functionality
if paste_button:
    st.experimental_set_query_params(url=url_input)  # This will update the URL field with pasted URL from clipboard

# Fetch the default number of pages dynamically only if URL is provided
default_pages = None
if url_input:
    st.write("Fetching max pages for the thread...")
    try:
        default_pages = asyncio.run(get_max_pages(clean_url(url_input)))
        st.write(f"Max pages detected: {default_pages}")
    except Exception as e:
        st.warning(f"Could not determine max pages: {e}")
        default_pages = 1

# Input for number of pages with default option "All"
pages_input = st.selectbox(
    "Pages to scrape:",
    ["All"] + [str(i) for i in range(1, default_pages + 1)] if default_pages else ["1"]
)
model_choice = st.radio("Model:", [("gpt-4", "Accurate (Default)"), ("gpt-3.5-turbo", "Faster")], format_func=lambda x: x[1])

# Main scraping and analysis logic
if url_input and st.button("Start"):
    with st.spinner("Processing..."):
        try:
            pages_to_scrape = default_pages if pages_input == "All" else int(pages_input)
            scraped_pages = asyncio.run(scrape_pages(clean_url(url_input), pages_to_scrape))
            posts = [post for _, content in scraped_pages for post in parse_posts(content, url_input)]
            st.write(f"Processed {len(posts)} posts from {pages_to_scrape} pages.")
            st.subheader("Analysis Summary")
            st.write(analyze_posts(posts, model_choice[0]))
        except Exception as e:
            st.error(f"An error occurred: {e}")
