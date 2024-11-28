# Forum Analyzer (for RFD = RedFlagDeals)
**Forum Analyzer** is a streamlined tool designed to analyze online forum threads for deals, strategies, and insights. It leverages asynchronous scraping for speed and OpenAI's GPT models for powerful analysis.

---

## Features

- **Effortless Input**: Paste forum URLs and easily trigger analysis with a single click.
- **Smart Scraping**: Supports multi-page scraping with dynamic page count detection.
- **Efficient Parsing**: Extracts posts along with their timestamps and direct hyperlinks.
- **Insightful Analysis**:
  - Summarizes key deals and navigation paths.
  - Highlights fringe benefits and unique strategies.
  - Identifies the best deal options with actionable steps.
- **Customizable AI Models**: Choose between speed (`gpt-3.5-turbo`) and accuracy (`gpt-4`).
- **Follow-Up Questions**: Ask additional questions or customize analysis in real-time.

---

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/forum-analyzer.git
   cd forum-analyzer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your OpenAI API key:
   - Go to the **Secrets Manager** on [Streamlit Cloud](https://streamlit.io/cloud).
   - Add your OpenAI API key as `OPENAI_API_KEY="XXX"`.

4. Run the app:
   ```bash
   streamlit run app.py
   ```

---

## How It Works
1. Enter a forum URL in the input field.
2. Choose the number of pages to scrape (default: all pages).
3. Select your preferred AI model.
4. The app:
   - Scrapes forum posts asynchronously for speed.
   - Analyzes the content and provides actionable insights.
   - Allows further customization via follow-up questions.

---

## Example Output
- **Summarized Deals**: Key deals and strategies extracted from the thread.
- **Best Negotiation Paths**: Tips for achieving the best value.
- **Citations**: Hyperlinked references to specific forum posts.

---

## Contributing
We welcome contributions! If you'd like to enhance or modify the app, feel free to fork this repository and submit a pull request.

---

## License
This project is licensed under the [MIT License](LICENSE).
