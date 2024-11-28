import aiohttp
import asyncio
import streamlit as st
from bs4 import BeautifulSoup
import re
from time import time
from datetime import datetime
import openai

# OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Headers to mimic a browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Semaphore to throttle requests
semaphore = asyncio.Semaphore(200)

# Async function to fetch a webpage
async def fetch_page(session, url):
    async with semaphore:
        async with session.get(url, headers=headers) as response:
            return await response.text()

# Determine the maximum number of pages to scrape
async def get_max_pages(base_url):
    async with aiohttp.ClientSession(headers=headers) as session:
        page_content = await fetch_page(session, base_url)
        soup = BeautifulSoup(page_content, 'html.parser')
        last_page = soup.find('a', string=re.compile(r'\d+$'))
        if last_page:
            return int(last_page.string)
        return 1

# Scrape posts from a single page
async def scrape_page(session, page_num, base_url):
    page_url = f"{base_url}/{page_num}/"
    page_content = await fetch_page(session, page_url)
    soup = BeautifulSoup(page_content, 'html.parser')
    posts = soup.find_all('section', class_='post_body')

    posts_details = []
    for post in posts:
        content_div = post.find('div', class_='content')
        content = content_div.get_text(strip=True) if content_div else "No content"
        post_number = post.get('data-post-number')  # Adjust based on forum structure
        timestamp_div = post.find('time')
        timestamp = timestamp_div.get('datetime') if timestamp_div else "Unknown"
        post_link = post.find('a', class_='post_permalink')
        post_url = post_link.get('href') if post_link else f"{base_url}#{post_number}"
        posts_details.append((post_number, timestamp, post_url, content))
    return posts_details

# Scrape multiple pages
async def scrape_forum_pages(base_url, pages_to_scrape):
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [
            scrape_page(session, page_num, base_url)
            for page_num in range(1, pages_to_scrape + 1)
        ]

        all_posts = []
        for i, task in enumerate(asyncio.as_completed(tasks), start=1):
            page_posts = await task
            all_posts.extend(page_posts)
            st.progress(i / pages_to_scrape)  # Update progress in Streamlit
        return all_posts

# Analyze posts with AI for decision-oriented insights
def ai_analyze_posts(posts):
    prompt = (
        "You are a decision-making assistant. Analyze the following forum posts "
        "and provide actionable insights. Extract:\n"
        "1. Key fringe deals or opportunities discussed.\n"
        "2. Concise recommendations based on the data.\n"
        "3. Summary of any risks or drawbacks.\n\n"
        + "\n\n".join(f"{num}\n{timestamp}\n{url}\n{content}" for num, timestamp, url, content in posts)
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a highly skilled analyst focused on delivering concise, actionable insights."},
            {"role": "user", "content": prompt}
        ]
    )
    return response["choices"][0]["message"]["content"]

# Streamlit UI for the app
st.title("Decision-Oriented Forum Scraper & Analyzer")

# Input URL and number of pages
base_url = st.text_input("Enter the forum URL:")
pages_input = st.text_input("Number of pages to scrape (leave blank for all):")

if st.button("Scrape and Analyze"):
    if base_url:
        with st.spinner("Scraping forum data..."):
            try:
                max_pages = asyncio.run(get_max_pages(base_url))
                pages_to_scrape = int(pages_input) if pages_input else max_pages
                posts = asyncio.run(scrape_forum_pages(base_url, pages_to_scrape))
                st.success(f"Scraped {len(posts)} posts from {pages_to_scrape} pages.")

                # Save scraped posts to a text file
                with open("scraped_posts.txt", "w", encoding="utf-8") as file:
                    file.write("\n---\n".join(
                        f"{num or 'N/A'}\n{timestamp}\n{url}\n{content}"
                        for num, timestamp, url, content in posts
                    ))

                # Analyze posts using AI
                with st.spinner("Analyzing posts with AI..."):
                    analysis = ai_analyze_posts(posts)
                st.subheader("AI Analysis")
                st.write(analysis)

                # Optional: Save AI analysis to a file
                with open("analysis.txt", "w", encoding="utf-8") as file:
                    file.write(analysis)

            except Exception as e:
                st.error(f"An error occurred: {e}")
    else:
        st.error("Please enter a valid URL.")
