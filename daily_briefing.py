import os, time, requests, smtplib
from dotenv import load_dotenv
from slack_sdk import WebClient
from email.message import EmailMessage
from langchain.llms import GoogleGemini
from langchain.tools import DuckDuckGoSearchRun
from langchain.agents import initialize_agent, Tool
import schedule

# ——— Load config ———
load_dotenv()
API_KEY    = os.getenv("GOOGLE_API_KEY")
SLACK_WEB  = os.getenv("SLACK_WEBHOOK_URL")
SMTP_SRV   = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_ADDR = os.getenv("EMAIL_ADDRESS")
EMAIL_PASS = os.getenv("EMAIL_PASSWORD")

# ——— LLM & Tools ———
llm = GoogleGemini(api_key=API_KEY, model="gemini-1.5-pro")
search_tool = DuckDuckGoSearchRun()
tools = [
    Tool(name="fetch_headlines", func=search_tool.run,
         description="Get today's top news headlines"),
    Tool(name="fact_check",     func=search_tool.run,
         description="Verify a given claim by searching online"),
]
agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=False)

def run_briefing():
    # 1) Fetch & summarize
    raw = agent.run("fetch_headlines: top news today")
    summary = llm(f"Here are today’s headlines:\n{raw}\n\nWrite a concise, 3-bullet summary.")
    # 2) Fact-check each bullet
    results = []
    for line in summary.splitlines():
        if not line.startswith("-"): continue
        claim = line.lstrip("- ").strip()
        sources = agent.run(f"fact_check: {claim}")
        verdict = llm(f"Sources:\n{sources}\n\nIs “{claim}” supported? Answer True/False/Unverified and cite URLs.")
        results.append(f"{claim}\n→ {verdict}")
    # 3) Build full message
    full = "📰 *Daily Briefing* 📰\n\n" + summary + "\n\n🔍 *Fact-Check Results:*\n" + "\n\n".join(results)
    # 4) Send to Slack
    if SLACK_WEB:
        requests.post(SLACK_WEB, json={"text": full})
    # 5) Send Email
    if SMTP_SRV and EMAIL_ADDR and EMAIL_PASS:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = EMAIL_ADDR, EMAIL_ADDR, "Daily News Briefing"
        msg.set_content(full)
        with smtplib.SMTP_SSL(SMTP_SRV, 465) as s:
            s.login(EMAIL_ADDR, EMAIL_PASS)
            s.send_message(msg)

if __name__ == "__main__":
    # Run once immediately
    run_briefing()
    # —OR— keep the script alive and schedule daily at 08:00
    schedule.every().day.at("08:00").do(run_briefing)
    while True:
        schedule.run_pending()
        time.sleep(30)
