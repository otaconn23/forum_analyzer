import streamlit as st
import aiohttp
import asyncio
import openai
import re
from bs4 import BeautifulSoup

# Configure OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Headers for web requests
headers = {"User-Agent": "Mozilla/5.0"}

async def fetch_page_async(session, url):
    """Fetch a single page asynchronously."""
    try:
        async with session.get(url, timeout=10) as response:
            return await response.text()
    except asyncio.TimeoutError:
        return f"Error: Timeout occurred for URL {url}"
    except Exception as e:
        return f"Error: {e}"

async def get_max_pages_async(base_url):
    """Fetch the maximum number of pages in the forum thread."""
    async with aiohttp.ClientSession(headers=headers) as session:
        page_content = await fetch_page_async(session, base_url)
        soup = BeautifulSoup(page_content, "lxml")  # Use lxml parser

        # Find all pagination links
        pagination_links = soup.find_all("a", href=True, string=re.compile(r"^\d+$"))
        page_numbers = [int(link.get_text(strip=True)) for link in pagination_links if link.get_text(strip=True).isdigit()]

        # Return the maximum page number or 1 if not found
        return max(page_numbers) if page_numbers else 1

async def scrape_forum_pages_async(base_url, pages_to_scrape):
    """Scrape forum pages asynchronously."""
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [
            fetch_page_async(session, f"{base_url}/{i}")
            for i in range(1, pages_to_scrape + 1)
        ]
        results = await asyncio.gather(*tasks)
    return results

def parse_posts(page_content):
    """Parses forum posts from page content."""
    soup = BeautifulSoup(page_content, "lxml")  # Explicitly use lxml parser
    return [post.get_text(strip=True) for post in soup.find_all("section", class_="post_body")]

def analyze_posts(posts, model):
    """Analyze posts using OpenAI API."""
    chunk_size = 50  # Adjust chunk size based on OpenAI token limits
    chunks = ["\n".join(posts[i:i + chunk_size]) for i in range(0, len(posts), chunk_size)]
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

def chat_with_ai(prompt, model):
    """Interact with OpenAI via a custom prompt."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant providing detailed and accurate responses."},
        {"role": "user", "content": prompt}
    ]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages
    )
    return response['choices'][0]['message']['content'].strip()

# Streamlit app interface
st.title("Enhanced Forum Analyzer with Chat (Async)")

# Input for forum URL
url = st.text_input("Enter the forum URL:")

# Fetch the default number of pages dynamically
default_pages = None
if url:
    st.write("Fetching max pages for the thread...")
    try:
        default_pages = asyncio.run(get_max_pages_async(url))
        st.write(f"Max pages detected: {default_pages}")
    except Exception as e:
        st.warning(f"Could not determine max pages: {e}")
        default_pages = 1

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
            pages_to_scrape = default_pages if pages_input == "all" else int(pages_input)
            page_contents = asyncio.run(scrape_forum_pages_async(url, pages_to_scrape))
            posts = list(set(post for page in page_contents for post in parse_posts(page)))

            if posts:
                st.write(f"Scraped {len(posts)} posts!")
                summary = analyze_posts(posts, selected_model)
                st.subheader("Analysis Summary")
                st.write(summary)

                # Chat bar for follow-up questions
                st.subheader("Customize Your Analysis")
                chat_input = st.text_input("Ask a follow-up question or customize the analysis:")
                if chat_input:
                    with st.spinner("Processing your query..."):
                        chat_response = chat_with_ai(chat_input, selected_model)
                        st.write(chat_response)

            else:
                st.warning("No posts found. Please check the URL.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
