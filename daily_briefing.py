import os
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from newsapi import NewsApiClient
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import initialize_agent, Tool
import schedule 
# from judgeval.tracer import Tracer, wrap

# judgment = Tracer(project_name="daily_briefing_agent")

load_dotenv()
API_KEY      = os.getenv("GOOGLE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
SMTP_SRV     = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_ADDR   = os.getenv("EMAIL_ADDRESS")
EMAIL_PASS   = os.getenv("EMAIL_PASSWORD")

#Initialize NewsAPI for real headlines
news = NewsApiClient(api_key=NEWS_API_KEY)

#Initialize search tool for fact-checking 
search_tool = DuckDuckGoSearchRun()

#Initialize Gemini LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    google_api_key=API_KEY
)

#fact-checking agent
tools = [
    Tool(
        name="fact_check",
        func=search_tool.run,
        description="Verify a given claim by searching online"
    )
]
agent = initialize_agent(
    tools,
    llm,
    agent="zero-shot-react-description",
    verbose=False
)

# @judgment.observe(span_type="function")
def make_prompt(raw: str, n: int) -> str:
    summary_fmt = "\n".join("- …" for _ in range(n))
    fact_fmt = "\n".join(f"{i+1}. …: True/False/Unverified (url)" for i in range(n))
    return (
        f"Here are today’s top {n} headlines:\n\n"
        f"{raw}\n\n"
        "TASK:\n"
        f"1. Write a concise, {n}-bullet summary of the main points.\n"
        f"2. For each bullet, fact-check it (True/False/Unverified + cite URLs).\n\n"
        "FORMAT:\n"
        "Summary:\n"
        f"{summary_fmt}\n\n"
        "Fact-Check:\n"
        f"{fact_fmt}\n"
    )

# @judgment.observe(span_type="function")
def run_briefing():
    # fetch top headlines
    top_headlines = news.get_top_headlines(country="us", page_size=5)
    articles = top_headlines.get("articles", [])
    raw = "\n".join(f"{i+1}. {a['title']}" for i, a in enumerate(articles))
    n = len(articles)

    prompt = make_prompt(raw, n)

    # single Gemini call
    resp = llm.invoke(prompt)
    full_message = resp.content.strip()

    # send via email
    if SMTP_SRV and EMAIL_ADDR and EMAIL_PASS:
        msg = EmailMessage()
        msg["From"]    = EMAIL_ADDR
        msg["To"]      = EMAIL_ADDR
        msg["Subject"] = "📰 Daily Briefing"
        msg.set_content(full_message)
        with smtplib.SMTP_SSL(SMTP_SRV, 465) as smtp:
            smtp.login(EMAIL_ADDR, EMAIL_PASS)
            smtp.send_message(msg)

    # debug output
    print(full_message)

if __name__ == "__main__":
    #To run immediately:
    run_briefing()
    #To schedule daily:
    # schedule.every().day.at("08:00").do(run_briefing)
    # while True:
    #     schedule.run_pending()
        # time.sleep(30)