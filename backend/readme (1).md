<h1 align="center">Company News Sentiment Analysis Tool</h1>

<p align="center">
  This project is a web-based application that extracts key details from multiple news articles related to a given company, performs sentiment analysis, conducts a comparative analysis, and generates a text-to-speech (TTS) output in Hindi. The tool allows users to input a company name and receive a structured sentiment report along with an audio output.
</p>

---

<h2>Features</h2>

<ul>
  <li>
    <strong>News Extraction:</strong>
    <ul>
      <li>Fetches news articles from either <strong>NewsAPI</strong> or <strong>Bing News RSS</strong> based on user selection.</li>
      <li>Extracts article titles, summaries, URLs, and publish dates.</li>
      <li>Scrapes full article content using <strong>BeautifulSoup</strong> (for RSS scraping).</li>
    </ul>
  </li>
  <li>
    <strong>Sentiment Analysis:</strong>
    <ul>
      <li>Uses the <strong>Groq API</strong> with the <strong>Qwen-2.5-32b model</strong> to analyze sentiment for each article.</li>
      <li>Provides sentiment scores (ranging from -1 to +1) and categorizes sentiment as Positive, Negative, or Neutral.</li>
    </ul>
  </li>
  <li>
    <strong>Summarization:</strong>
    <ul>
      <li>Combines individual article summaries and sentiment scores into an overall summary using the <strong>qwen-2.5 model via the Groq API</strong>.</li>
    </ul>
  </li>
  <li>
    <strong>Comparative Analysis:</strong>
    <ul>
      <li>Compares sentiment across articles and generates a pie chart showing sentiment distribution.</li>
      <li>Highlights key topics covered in the articles.</li>
    </ul>
  </li>
  <li>
    <strong>Hindi Text-to-Speech (TTS):</strong>
    <ul>
      <li>Translates the overall summary into Hindi using <strong>googletrans</strong>.</li>
      <li>Converts the Hindi text into an audio file using <strong>gTTS</strong>.</li>
    </ul>
  </li>
  <li>
    <strong>User Interface:</strong>
    <ul>
      <li>Built using <strong>Streamlit</strong>, providing a simple and interactive web interface.</li>
      <li>Users can input a company name, select a news source, and view the sentiment report.</li>
    </ul>
  </li>
</ul>

---

<h2>Implementation</h2>

<h3>Modules</h3>

<ul>
  <li>
    <strong><code>news_fetcher.py</code>:</strong>
    <ul>
      <li>Fetches news articles using <strong>NewsAPI</strong>.</li>
      <li>Scrapes full article content from the article URLs.</li>
    </ul>
  </li>
  <li>
    <strong><code>news_fetcher2.py</code>:</strong>
    <ul>
      <li>Fetches news articles using <strong>Bing News RSS</strong>.</li>
      <li>Uses <strong>BeautifulSoup</strong> to scrape article content.</li>
    </ul>
  </li>
  <li>
    <strong><code>sentiment_analysis.py</code>:</strong>
    <ul>
      <li>Performs sentiment analysis on article content using the <strong>Qwen-2.5-32b via the Groq API</strong>.</li>
      <li>Returns sentiment scores, summaries, and keywords.</li>
    </ul>
  </li>
  <li>
    <strong><code>summarizer.py</code>:</strong>
    <ul>
      <li>Combines individual article summaries and sentiment scores into an overall summary using the <strong>Groq API</strong>.</li>
    </ul>
  </li>
  <li>
    <strong><code>tts.py</code>:</strong>
    <ul>
      <li>Translates the overall summary into Hindi using <strong>googletrans</strong>.</li>
      <li>Generates a Hindi audio file using <strong>gTTS</strong>.</li>
    </ul>
  </li>
  <li>
    <strong><code>app.py</code>:</strong>
    <ul>
      <li>The main Streamlit application.</li>
      <li>Integrates all modules and provides a user-friendly interface.</li>
    </ul>
  </li>
</ul>

---

<h2>Dependencies</h2>

<h3>Python Libraries</h3>

<ul>
  <li><strong>Streamlit</strong>: For building the web interface.</li>
  <li><strong>requests</strong>: For making HTTP requests to NewsAPI and scraping article content.</li>
  <li><strong>BeautifulSoup</strong>: For parsing HTML content during RSS scraping.</li>
  <li><strong>googletrans</strong>: For translating text to Hindi.</li>
  <li><strong>gTTS</strong>: For generating Hindi audio files.</li>
  <li><strong>matplotlib</strong>: For generating pie charts.</li>
  <li><strong>groq</strong>: For interacting with the Qwen-2.5 model for sentiment analysis and summarization.</li>
  <li><strong>asyncio</strong>: For handling asynchronous tasks like translation and TTS.</li>
</ul>

<h3>APIs</h3>

<ul>
  <li><strong>NewsAPI</strong>: For fetching news articles.</li>
  <li><strong>Qwen-2.5-32b via Groq Cloud API</strong>: For sentiment analysis and summarization.</li>
</ul>

---

<h2>Setup Instructions</h2>

<ol>
  <li>
    <strong>Clone the Repository</strong>
    <pre><code>git clone https://github.com/arunima-anil/News_summarization.git
cd News_summarization</code></pre>
  </li>
  <li>
    <strong>Install Dependencies</strong>
    <p>Create a virtual environment and install the required Python packages:</p>
    <pre><code>python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt</code></pre>
  </li>
  <li>
    <strong>Set Up API Keys</strong>
    <ul>
      <li>
        <strong>NewsAPI</strong>:
        <ul>
          <li>Sign up at <a href="https://newsapi.org/">NewsAPI</a> and get your API key.</li>
          <li>Place the <code>NEWS_API_KEY</code> in <code>news_fetcher.py</code> </li>
        </ul>
      </li>
      <li>
        <strong>Groq API</strong>:
        <ul>
          <li>Sign up at <a href="https://groq.com/">Groq</a> and get your API key.</li>
          <li>Place the <code>api_key</code> in <code>sentiment_analysis.py</code> and <code>summarizer.py</code> </li>
        </ul>
      </li>
    </ul>
  </li>
  <li>
    <strong>Run the Application</strong>
    <p>Start the Streamlit app:</p>
    <pre><code>streamlit run app.py</code></pre>
    <p>The app will open in your browser at <a href="http://localhost:8501">http://localhost:8501</a>.</p>
    <p>Deployment link in hugging face <a href="https://huggingface.co/spaces/unni69/news_summarization_streamlit">https://huggingface.co/spaces/unni69/news_summarization_streamlit</a>.</p>
  </li>
</ol>

---

<h2>Usage</h2>

<ol>
  <li>
    <strong>Enter Company Name</strong>:
    <ul>
      <li>Input the name of the company you want to analyze (e.g., "Reliance Industries").</li>
    </ul>
  </li>
  <li>
    <strong>Select News Source</strong>:
    <ul>
      <li>Choose between <strong>NewsAPI</strong> or <strong>Bing Scrape</strong> to fetch news articles.</li>
    </ul>
  </li>
  <li>
    <strong>Generate Report</strong>:
    <ul>
      <li>Click the "Generate Report" button to fetch articles, analyze sentiment, and generate the Hindi audio.</li>
    </ul>
  </li>
  <li>
    <strong>View Results</strong>:
    <ul>
      <li>The app will display:
        <ul>
          <li>Article summaries and sentiment analysis.</li>
          <li>Overall sentiment score and summary.</li>
          <li>A pie chart showing sentiment distribution.</li>
          <li>A playable Hindi audio summary.</li>
        </ul>
      </li>
    </ul>
  </li>
</ol>

---

<h2>Example Output</h2>

<ul>
  <li>
    <strong>Article Summaries and Sentiment Analysis</strong>:
    <ul>
      <li><strong>Title</strong>: Reliance Industries reports record profits</li>
      <li><strong>Sentiment Score</strong>: 0.8 (Positive)</li>
      <li><strong>Summary</strong>: Reliance Industries reported a 20% increase in profits this quarter.</li>
      <li><strong>Keywords</strong>: profits, growth, financial performance</li>
    </ul>
  </li>
  <li>
    <strong>Overall News Summary and Sentiment</strong>:
    <ul>
      <li><strong>Overall Sentiment Score</strong>: 0.65 (Positive)</li>
      <li><strong>Overall Summary</strong>: Reliance Industries has shown strong financial performance this quarter, with a 20% increase in profits. The company's announcement to expand into European markets further underscores its growth trajectory. However, it faces criticism from environmental groups regarding its carbon emissions.</li>
    </ul>
  </li>
  <li>
    <strong>Sentiment Distribution</strong>:
    <ul>
      <li><strong>Positive</strong>: 70%</li>
      <li><strong>Negative</strong>: 20%</li>
      <li><strong>Neutral</strong>: 10%</li>
    </ul>
  </li>
  <li>
    <strong>Hindi Audio Summary</strong>:
    <ul>
      <li>A playable audio file summarizing the report in Hindi.</li>
    </ul>
  </li>
</ul>

---

<h2>Acknowledgments</h2>

<ul>
  <li><strong>NewsAPI</strong> for providing news data.</li>
  <li><strong>Groq</strong> for the Qwen API.</li>
  <li><strong>Streamlit</strong> for the web interface framework.</li>
</ul>
