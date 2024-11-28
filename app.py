import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import openai
import streamlit as st

# Function to test OpenAI API key
def test_openai_api_key(api_key):
    """Test the OpenAI API key by making a minimal request."""
    try:
        openai.api_key = api_key
        # Send a simple request to verify the API key
        openai.Completion.create(
            model="text-davinci-003",
            prompt="Test API connection",
            max_tokens=5
        )
        return True
    except openai.error.AuthenticationError:
        st.error("Invalid OpenAI API key. Please check your key.")
        return False
    except Exception as e:
        st.error(f"An error occurred while testing the API key: {e}")
        return False

# Headers to mimic a browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Semaphore to throttle requests
semaphore = asyncio.Semaphore(200)

async def fetch_page(session, url):
    """Fetch a single page."""
    async with semaphore:
        async with session.get(url, headers=headers) as response:
            return await response.text()

async def get_max_pages(base_url):
    """Determine the maximum number of pages."""
    async with aiohttp.ClientSession(headers=headers) as session:
        page_content = await fetch_page(session, base_url)
        soup = BeautifulSoup(page_content, 'html.parser')

        # Look for pagination_last to get the max page number
        last_page_link = soup.select_one("a.pagination_last")
        if last_page_link:
            match = re.search(r"\d+", last_page_link.get("href", ""))
            if match:
                return int(match.group(0))
        
        # If pagination_last is not found, fall back to pagination_pages
        page_links = soup.select("ul.pagination_pages a")
        return max((int(a.get_text(strip=True)) for a in page_links if a.get_text(strip=True).isdigit()), default=1)

async def scrape_page(session, page_num, base_url):
    """Scrape a single page for posts."""
    page_url = f"{base_url}/{page_num}/"
    page_content = await fetch_page(session, page_url)
    soup = BeautifulSoup(page_content, 'html.parser')
    posts = soup.find_all('section', class_='post_body')

    posts_details = []
    for post in posts:
        # Extract content
        content_div = post.find('div', class_='content')
        content = content_div.get_text(strip=True) if content_div else "No content"

        # Extract post number and URL
        permalink = post.find('a', class_='dateline_permalink')
        post_number = permalink.get_text(strip=True) if permalink else "N/A"
        post_url = permalink.get("href") if permalink else f"{base_url}#{post_number}"

        # Extract timestamp
        timestamp_div = post.find('span', class_='dateline_timestamp')
        timestamp = timestamp_div.get_text(strip=True) if timestamp_div else "Unknown"

        # Append the details as a formatted string
        posts_details.append(f"[Post {post_number or 'N/A'}]({post_url})\n{timestamp}\n{content}")
    return posts_details

async def scrape_forum_pages(base_url, pages_to_scrape):
    """Scrape all specified pages and keep posts in memory."""
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [
            scrape_page(session, page_num, base_url)
            for page_num in range(1, pages_to_scrape + 1)
        ]

        all_posts = []
        for i, task in enumerate(asyncio.as_completed(tasks), start=1):
            page_posts = await task
            all_posts.extend(page_posts)
            st.write(f"Scraped page {i}/{pages_to_scrape}")
        return all_posts

def analyze_posts(posts_content):
    """Generate AI-driven insights from the in-memory posts."""
    prompt = (
        "You are a decision-making assistant. Based on the following forum posts, "
        "generate actionable insights. Provide:\n"
        "1. Key deals or opportunities discussed.\n"
        "2. Risks or drawbacks mentioned.\n"
        "3. A concise, fact-based recommendation.\n\n"
        f"{posts_content}"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a highly skilled analyst focused on delivering concise, actionable insights."},
            {"role": "user", "content": prompt}
        ]
    )
    return response["choices"][0]["message"]["content"]

async def run_app():
    """Run the scraping and AI analysis app with Streamlit."""
    st.title("Forum Scraper & AI Analyzer")
    
    # Inputs
    base_url = st.text_input("Enter the forum URL (without trailing page number):")
    pages_input = st.text_input("How many pages to scrape? (leave blank for default):")
    api_key_input = st.text_input("Enter your OpenAI API Key:", type="password")
    
    if st.button("Start Scraping"):
        if not base_url:
            st.error("Please enter a valid forum URL.")
            return

        # Test the API key
        st.write("Testing OpenAI API key...")
        if not test_openai_api_key(api_key_input):
            return  # Stop execution if the key is invalid

        st.write("OpenAI API key is valid. Determining maximum pages...")
        max_pages = await get_max_pages(base_url)
        pages_to_scrape = int(pages_input) if pages_input.isdigit() else max_pages

        st.write(f"Scraping {pages_to_scrape} pages...")
        posts = await scrape_forum_pages(base_url, pages_to_scrape)

        st.write(f"Scraped {len(posts)} posts. Generating AI analysis...")
        posts_content = "\n---\n".join(posts)
        analysis = analyze_posts(posts_content)

        st.subheader("AI Analysis")
        st.write(analysis)

# Streamlit-compatible execution
def main():
    asyncio.run(run_app())

if __name__ == "__main__":
    main()
