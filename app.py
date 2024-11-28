import aiohttp
import asyncio
import streamlit as st
from bs4 import BeautifulSoup
import re
from time import time
from datetime import datetime
import pandas as pd

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
        posts_details.append({
            "Post Number": post_number if post_number else "N/A",
            "Timestamp": timestamp,
            "URL": post_url,
            "Content": content,
        })
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

# Streamlit App
st.title("Forum Scraper")
st.write("Scrape forum posts and export the data for further analysis.")

# Input URL and optional page count
base_url = st.text_input("Enter the forum URL:")
pages_input = st.text_input("Number of pages to scrape (leave blank for all):")

if st.button("Start Scraping"):
    if base_url:
        with st.spinner("Scraping forum data..."):
            try:
                # Determine the number of pages to scrape
                max_pages = asyncio.run(get_max_pages(base_url))
                pages_to_scrape = int(pages_input) if pages_input else max_pages

                # Scrape forum data
                posts = asyncio.run(scrape_forum_pages(base_url, pages_to_scrape))

                # Convert to DataFrame for display and download
                df = pd.DataFrame(posts)
                st.success(f"Scraped {len(posts)} posts from {pages_to_scrape} pages.")
                st.dataframe(df)  # Display scraped data

                # Add download button
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download Data as CSV",
                    data=csv,
                    file_name="scraped_posts.csv",
                    mime="text/csv",
                )

            except Exception as e:
                st.error(f"An error occurred: {e}")
    else:
        st.error("Please enter a valid URL.")
