import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import openai

# OpenAI API key
openai.api_key = "your-openai-api-key"

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
            print(f"Scraped page {i}/{pages_to_scrape}")
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

async def main():
    """Main function to scrape forum data and generate insights."""
    base_url = input("Please enter the forum URL (without trailing page number): ")
    max_pages = await get_max_pages(base_url)
    
    # Allow user to specify number of pages, default to max_pages
    pages_input = input(f"How many pages to scrape? (default={max_pages}): ").strip()
    pages_to_scrape = int(pages_input) if pages_input else max_pages

    print("Scraping forum data...")
    posts = await scrape_forum_pages(base_url, pages_to_scrape)

    # Join all posts for AI processing
    posts_content = "\n---\n".join(posts)
    print("Generating AI analysis...")

    # AI analysis
    analysis = analyze_posts(posts_content)
    print("\nAI Analysis:\n")
    print(analysis)

# Updated execution for Python 3.12+
if __name__ == "__main__":
    asyncio.run(main())
