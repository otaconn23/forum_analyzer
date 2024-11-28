import streamlit as st
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import openai
import re

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Headers to mimic a browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

semaphore = asyncio.Semaphore(50)  # Limit concurrency


async def fetch_page(session, url):
    async with semaphore:
        async with session.get(url) as response:
            return await response.text()


async def scrape_forum_pages(base_url, pages_to_scrape=None):
    async with aiohttp.ClientSession(headers=headers) as session:
        # Assume a single-page forum for simplicity; add pagination logic if needed
        page_content = await fetch_page(session, base_url)
        soup = BeautifulSoup(page_content, "html.parser")
        posts = soup.find_all("section", class_="post_body")
        return [post.get_text(strip=True) for post in posts]


def analyze_posts(posts):
    combined_posts = "\n".join(posts[:50])  # Use the first 50 posts for analysis
    messages = [
        {"role": "system", "content": "You are a helpful assistant that summarizes forum discussions."},
        {"role": "user", "content": (
            "Analyze the following forum posts:\n"
            "1. Summarize the deal being discussed.\n"
            "2. Extract user opinions (positive and negative).\n"
            "3. Provide your conclusion about the quality of the deal.\n\n"
            f"{combined_posts}"
        )}
    ]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"OpenAI API Error: {e}")
        return None


st.title("Forum Analyzer")
url = st.text_input("Enter the forum URL:")
pages_to_scrape = st.number_input("Number of pages to scrape:", min_value=1, value=1, step=1)

if url:
    try:
        st.write("Scraping forum data...")
        posts = asyncio.run(scrape_forum_pages(url, pages_to_scrape))
        if posts:
            st.write(f"Scraped {len(posts)} posts.")
            st.write("Analyzing posts...")
            summary = analyze_posts(posts)
            if summary:
                st.subheader("Summary")
                st.write(summary)

            # Allow follow-up questions
            user_question = st.text_input("Ask a follow-up question:")
            if user_question:
                followup_messages = [
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on forum discussions."},
                    {"role": "user", "content": (
                        f"Based on these forum posts:\n\n{posts[:50]}\n\n"
                        f"Answer this question: {user_question}"
                    )}
                ]
                try:
                    followup_response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=followup_messages
                    )
                    st.subheader("Follow-Up Answer")
                    st.write(followup_response['choices'][0]['message']['content'])
                except Exception as e:
                    st.error(f"OpenAI Follow-Up Error: {e}")
        else:
            st.warning("No posts were found.")
    except Exception as e:
        st.error(f"Error: {e}")
