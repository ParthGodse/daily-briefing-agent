import os
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage
from typing import TypedDict
import re

from newsapi import NewsApiClient
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, Tool

from langgraph.graph import StateGraph, START, END
from judgeval.common.tracer import Tracer
from judgeval.integrations.langgraph import JudgevalCallbackHandler
from judgeval.scorers import AnswerRelevancyScorer, FaithfulnessScorer

load_dotenv()
judgment = Tracer(
    project_name="daily_briefing_agent",
    api_key=os.getenv("JUDGMENT_API_KEY")
)
handler = JudgevalCallbackHandler(judgment)

API_KEY      = os.getenv("GOOGLE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
SMTP_SRV     = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_ADDR   = os.getenv("EMAIL_ADDRESS")
EMAIL_PASS   = os.getenv("EMAIL_PASSWORD")

news_client = NewsApiClient(api_key=NEWS_API_KEY)
search_tool = DuckDuckGoSearchRun()
llm         = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    google_api_key=API_KEY
)
tools = [
    Tool(
        name="fact_check",
        func=search_tool.run,
        description="Verify a given claim by searching online"
    )
]
agent = initialize_agent(
    tools, llm,
    agent="zero-shot-react-description",
    verbose=False
)

class BriefingState(TypedDict):
    headlines:   str
    summary:     str
    fact_checks: str

graph = StateGraph(BriefingState)

def fetch_headlines(state: BriefingState) -> BriefingState:
    resp   = news_client.get_top_headlines(country="us", page_size=5)
    titles = [f"{i+1}. {a['title']}" for i,a in enumerate(resp["articles"])]
    state["headlines"] = "\n".join(titles)
    return state
graph.add_node("fetch", fetch_headlines)

def summarize(state: BriefingState) -> BriefingState:
    prompt = f"""Here are today’s headlines:

{state["headlines"]}

Write a concise, 5-bullet summary of the main points."""
    out = llm.invoke(prompt)
    summary = out.content.strip()
    state["summary"] = summary

    judgment.async_evaluate(
        scorers=[AnswerRelevancyScorer(threshold=0.7)],
        input=state["headlines"],
        actual_output=summary,
        model="gemini-1.5-pro",
    )

    return state

graph.add_node("summarize", summarize)

def fact_check(state: BriefingState) -> BriefingState:
    checks = []
    for line in state["summary"].splitlines():
        if not (line.startswith("- ") or line.startswith("* ")):
            continue
        claim = line[2:].strip()
        resp = llm.invoke(
            f"Fact-Check: “{claim}”\n"
            "Answer in this exact format:\n"
            "<True/False/Unverified> (<URL>)"
        )
        verdict = resp.content.strip()
        checks.append(f"{claim} → {verdict}")
        judgment.async_evaluate(
            scorers=[FaithfulnessScorer()],
            input=claim,
            actual_output=verdict,
            model="gemini-1.5-pro",
        )

    state["fact_checks"] = "\n\n".join(checks)
    return state

graph.add_node("fact_check", fact_check)

graph.add_edge(START, "fetch")
graph.add_edge("fetch", "summarize")
graph.add_edge("summarize", "fact_check")
graph.add_edge("fact_check", END)

app = graph.compile()

def run_briefing():
    initial = BriefingState(headlines="", summary="", fact_checks="")
    final = app.invoke(initial, config={"callbacks": [handler]})

    raw_summary = final["summary"]
    lines = raw_summary.splitlines()

    bullets = []
    current = None
    for line in lines:
        # detect start of a new bullet if it begins with “- ” or “* ”
        if re.match(r'^[\-\*]\s', line):
            if current is not None:
                bullets.append(current)
            # strip the leading bullet marker and any bold stars
            text = re.sub(r'^[\-\*]\s+', '', line)
            text = text.replace("**", "")
            current = text.strip()
        else:
            if current is not None:
                current += " " + line.strip()
    if current:
        bullets.append(current)

    fact_checks = []
    body = "📰 *Daily Briefing* 📰\n\nSummary:\n"
    for b in bullets:
        body += f"- {b}\n"
    body += "\nFact-Check:\n"
    for idx, claim in enumerate(bullets, 1):
        resp = llm.invoke(
            f"Fact-Check: “{claim}”\n"
            "Answer in this exact format:\n"
            "<True/False/Unverified> (<URL>)"
        )
        verdict = resp.content.strip()
        fact_checks.append((claim, verdict))
        body += f"{idx}. {claim} → {verdict}\n"

    if SMTP_SRV and EMAIL_ADDR and EMAIL_PASS:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = (
            EMAIL_ADDR, EMAIL_ADDR, "📰 Daily Briefing"
        )
        msg.set_content(body)
        with smtplib.SMTP_SSL(SMTP_SRV, 465) as smtp:
            smtp.login(EMAIL_ADDR, EMAIL_PASS)
            smtp.send_message(msg)

    # Print the briefing + trace info
    print(body)
    print("Executed Nodes:", handler.executed_nodes)
    print("Executed Tools:", handler.executed_tools)
    print("Node/Tool Flow:", handler.executed_node_tools)

if __name__ == "__main__":
    run_briefing()