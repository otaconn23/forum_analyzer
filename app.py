import streamlit as st
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import openai
import re
from datetime import datetime

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Headers to mimic a browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

semaphore = asyncio.Semaphore(50)  # Limit concurrency for safety


# Function to fetch a single page
async def fetch_page(session, url):
    async with semaphore:
        async with session.get(url) as response:
            return await response.text()


# Function to determine the maximum number of pages
async def get_max_pages(base_url):
    async with aiohttp.ClientSession(headers=headers) as session:
        page_content = await fetch_page(session, base_url)
        soup = BeautifulSoup(page_content, "html.parser")
        last_page = soup.find("a", string=re.compile(r"\d+$"))
        if last_page:
            return int(last_page.string)
        return 1


# Function to scrape a single page
async def scrape_page(session, page_num, base_url):
    page_url = f"{base_url}/{page_num}/"
    page_content = await fetch_page(session, page_url)
    soup = BeautifulSoup(page_content, "html.parser")
    posts = soup.find_all("section", class_="post_body")
    posts_content = []
    for post in posts:
        content_div = post.find("div", class_="content")
        if content_div:
            posts_content.append(content_div.get_text(strip=True))
    return posts_content


# Function to scrape all forum pages
async def scrape_forum_pages(base_url, pages_to_scrape=None):
    max_pages = await get_max_pages(base_url)
    pages_to_scrape = pages_to_scrape or max_pages
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [
            scrape_page(session, page_num, base_url)
            for page_num in range(1, pages_to_scrape + 1)
        ]
        results = await asyncio.gather(*tasks)
    return [post for page_posts in results for post in page_posts]


# Function to analyze posts
def analyze_posts(posts):
    combined_posts = "\n".join(posts[:50])  # Analyze up to the first 50 posts
    messages = [
        {"role": "system", "content": "You are an assistant specialized in summarizing forum discussions."},
        {"role": "user", "content": (
            "Analyze the following forum posts. Identify:\n"
            "1. The deal being offered and its details.\n"
            "2. User feedback on the deal.\n"
            "3. Conclusions about whether the deal is worthwhile.\n"
            "4. Ignore outdated or irrelevant information.\n\n"
            f"{combined_posts}"
        )}
    ]
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    return response['choices'][0]['message']['content'].strip()


# Streamlit app interface
st.title("Forum Analyzer")
url = st.text_input("Enter the forum URL to analyze:")
pages_to_scrape = st.number_input("Number of pages to scrape (default = all):", min_value=1, step=1, value=1)

if url:
    try:
        # Scrape forum data
        st.write("Fetching and scraping forum posts...")
        posts = asyncio.run(scrape_forum_pages(url, pages_to_scrape))
        if posts:
            st.write(f"Scraped {len(posts)} posts!")
            
            # Analyze and summarize posts
            st.write("Analyzing posts with OpenAI...")
            summary = analyze_posts(posts)
            st.subheader("Analysis Summary:")
            st.write(summary)

            # Interactive chat for follow-ups
            user_question = st.text_input("Ask a follow-up question about the forum discussion:")
            if user_question:
                followup_messages = [
                    {"role": "system", "content": "You are an assistant specialized in answering questions about forum discussions."},
                    {"role": "user", "content": (
                        f"Based on the following forum posts:\n\n{posts[:50]}\n\n"
                        f"Answer the user's question: {user_question}"
                    )}
                ]
                followup_response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=followup_messages
                )
                st.subheader("Follow-up Answer:")
                st.write(followup_response['choices'][0]['message']['content'].strip())
        else:
            st.warning("No posts found. Please check the URL or try a different forum.")
    except Exception as e:
        st.error(f"An error occurred: {e}")
