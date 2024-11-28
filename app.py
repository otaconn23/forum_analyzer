import streamlit as st
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import openai
import re

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Headers for web requests
headers = {"User-Agent": "Mozilla/5.0"}

# Semaphore for concurrency
semaphore = asyncio.Semaphore(100)  # Increased for faster scraping


async def fetch_page(session, url):
    """Fetches a single page."""
    async with semaphore:
        try:
            async with session.get(url, timeout=10) as response:
                return await response.text()
        except asyncio.TimeoutError:
            st.warning(f"Timeout occurred for URL: {url}")
            return ""


async def scrape_forum_pages(base_url, pages_to_scrape=None):
    """Scrapes all forum pages up to the specified number."""
    async with aiohttp.ClientSession(headers=headers, connector=aiohttp.TCPConnector(keepalive_timeout=30)) as session:
        tasks = [fetch_page(session, f"{base_url}/{i}") for i in range(1, pages_to_scrape + 1)]
        results = await asyncio.gather(*tasks)
        return [post for result in results if result for post in parse_posts(result)]


def parse_posts(page_content):
    """Parses forum posts from page content using the lxml parser."""
    soup = BeautifulSoup(page_content, "lxml")  # Use lxml parser here
    return [post.get_text(strip=True) for post in soup.find_all("section", class_="post_body")]


def analyze_posts(posts):
    """Analyzes posts using OpenAI's API."""
    chunks = ["\n".join(posts[i:i + 10]) for i in range(0, len(posts), 10)]
    summaries = []
    for chunk in chunks:
        messages = [
            {"role": "system", "content": "You are an assistant that summarizes forum discussions."},
            {"role": "user", "content": (
                "Analyze the following forum posts:\n"
                "1. Summarize the deal.\n"
                "2. Extract user opinions (positive and negative).\n"
                "3. Provide conclusions about the deal's value.\n\n"
                f"{chunk}"
            )}
        ]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        summaries.append(response['choices'][0]['message']['content'].strip())
    return "\n\n".join(summaries)


# Streamlit app interface
st.title("Optimized Forum Analyzer")
url = st.text_input("Enter the forum URL:")
pages_to_scrape = st.number_input("Number of pages to scrape:", min_value=1, value=1, step=1)

if url:
    with st.spinner("Scraping and analyzing..."):
        try:
            posts = asyncio.run(scrape_forum_pages(url, pages_to_scrape))
            if posts:
                st.write(f"Scraped {len(posts)} posts!")
                summary = analyze_posts(posts)
                st.subheader("Analysis Summary")
                st.write(summary)
            else:
                st.warning("No posts found. Please check the URL.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
