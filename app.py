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
semaphore = asyncio.Semaphore(100)


async def fetch_page(session, url):
    """Fetches a single page."""
    async with semaphore:
        try:
            async with session.get(url, timeout=10) as response:
                return await response.text()
        except asyncio.TimeoutError:
            st.warning(f"Timeout occurred for URL: {url}")
            return ""


async def get_max_pages(base_url):
    """Fetches the maximum number of pages in the forum thread."""
    async with aiohttp.ClientSession(headers=headers) as session:
        page_content = await fetch_page(session, base_url)
        soup = BeautifulSoup(page_content, "lxml")
        # Modify this based on the forum's pagination structure
        last_page = soup.find("a", string=re.compile(r"\d+$"))
        if last_page:
            return int(last_page.string)
        return 1


async def scrape_forum_pages(base_url, pages_to_scrape):
    """Scrapes all forum pages up to the specified number."""
    async with aiohttp.ClientSession(headers=headers, connector=aiohttp.TCPConnector(keepalive_timeout=30)) as session:
        if pages_to_scrape == "all":
            # Dynamically fetch the maximum number of pages
            max_pages = await get_max_pages(base_url)
            pages_to_scrape = max_pages

        tasks = [fetch_page(session, f"{base_url}/{i}") for i in range(1, pages_to_scrape + 1)]
        results = await asyncio.gather(*tasks)
        return [post for result in results if result for post in parse_posts(result)]


def parse_posts(page_content):
    """Parses forum posts from page content using the lxml parser."""
    soup = BeautifulSoup(page_content, "lxml")  # Use lxml parser here
    return [post.get_text(strip=True) for post in soup.find_all("section", class_="post_body")]


def analyze_posts(posts, model):
    """Analyzes posts using OpenAI's API with the selected model."""
    chunks = ["\n".join(posts[i:i + 10]) for i in range(0, len(posts), 10)]
    summaries = []
    for chunk in chunks:
        messages = [
            {"role": "system", "content": "You are a helpful assistant summarizing forum discussions."},
            {"role": "user", "content": (
                "Analyze the following forum posts:\n"
                "1. Summarize the deal.\n"
                "2. Extract user opinions (positive and negative).\n"
                "3. Provide conclusions about the deal's value.\n\n"
                f"{chunk}"
            )}
        ]
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages
        )
        summaries.append(response['choices'][0]['message']['content'].strip())
    return "\n\n".join(summaries)


# Streamlit app interface
st.title("Optimized Forum Analyzer")

# Input for forum URL
url = st.text_input("Enter the forum URL:")

# Fetch the default number of pages dynamically
default_pages = None
if url:
    st.write("Fetching max pages for the thread...")
    try:
        default_pages = asyncio.run(get_max_pages(url))
        st.write(f"Max pages detected: {default_pages}")
    except Exception as e:
        st.warning(f"Could not determine max pages: {e}")

# Input for number of pages with default option "All"
pages_input = st.selectbox(
    "Number of pages to scrape:",
    options=["all"] + ([str(i) for i in range(1, default_pages + 1)] if default_pages else ["1"]),
    format_func=lambda x: "All" if x == "all" else x
)

# Model selection
model_choice = st.radio(
    "Choose a model:",
    options=[
        ("gpt-3.5-turbo", "Faster (Good for most tasks)"),
        ("gpt-4", "More Accurate (Better for complex tasks)")
    ],
    format_func=lambda x: x[1]
)
selected_model = model_choice[0]  # Get the actual model name (gpt-3.5-turbo or gpt-4)

# Main scraping and analysis logic
if url and pages_input:
    with st.spinner("Scraping and analyzing..."):
        try:
            posts = asyncio.run(scrape_forum_pages(url, pages_to_scrape="all" if pages_input == "all" else int(pages_input)))
            if posts:
                st.write(f"Scraped {len(posts)} posts!")
                summary = analyze_posts(posts, selected_model)
                st.subheader("Analysis Summary")
                st.write(summary)
            else:
                st.warning("No posts found. Please check the URL.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
