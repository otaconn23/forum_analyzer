import streamlit as st
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import openai

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# App title
st.title("Forum Analyzer")

# User input for the forum URL
url = st.text_input("Enter the forum URL to analyze:")

# Fetch and process forum data
async def fetch_forum_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            # Extract forum posts (modify selectors based on forum structure)
            posts = soup.find_all("div", class_="post-content")  # Example: update for actual forum
            return [post.get_text(strip=True) for post in posts]

# If a URL is provided, fetch and analyze the data
if url:
    st.write("Fetching forum data...")
    try:
        posts = asyncio.run(fetch_forum_data(url))
        if posts:
            st.write(f"Fetched {len(posts)} posts.")
            
            # Summarize using OpenAI
            st.write("Analyzing posts with OpenAI...")
            combined_posts = "\n".join(posts[:5])  # Analyze first 5 posts (for brevity)
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=f"Summarize the following forum discussion:\n\n{combined_posts}",
                max_tokens=300
            )
            st.write("Summary:")
            st.write(response.choices[0].text.strip())
        else:
            st.error("No posts found at the given URL.")
    except Exception as e:
        st.error(f"Error fetching data: {e}")
