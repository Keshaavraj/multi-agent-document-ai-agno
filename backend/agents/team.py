"""
Multi-Agent Team — CP07
Agno Team in route mode.
The Orchestrator reads the user query and routes to the best specialist:
  - RAG Agent      → specific questions, fact lookup, citations
  - Summary Agent  → overviews, key points, executive summaries
  - Analyst Agent  → tables, numbers, statistics, data extraction
"""

from agno.agent import Agent
from agno.team import Team
from agno.models.groq import Groq as GroqModel

from agents.rag_agent import create_rag_agent
from agents.summary_agent import create_summary_agent
from agents.analyst_agent import create_analyst_agent

ORCHESTRATOR_MODEL = "llama-3.3-70b-versatile"

ORCHESTRATOR_INSTRUCTIONS = """
You are the orchestrator of a document intelligence system.
Your only job is to route user queries to the correct specialist agent.

Routing rules:
- RAG Agent      → specific questions about content, fact lookups, "what does it say about X", "find X", "which page", "according to the document"
- Summary Agent  → "summarise", "overview", "what is this about", "key points", "main topics", "brief me", "tldr"
- Analyst Agent  → "table", "extract", "numbers", "statistics", "data", "list all", "compare", "how many", "percentage", "figures"

When in doubt, route to the RAG Agent.
Do NOT answer the question yourself — always delegate to a specialist.
"""

# Intent keywords for fast local routing (fallback if team routing is slow)
SUMMARY_KEYWORDS = {
    "summarise", "summarize", "summary", "overview", "brief", "tldr",
    "key points", "main topics", "what is this about", "what is this document",
    "introduction", "outline",
}
ANALYST_KEYWORDS = {
    "table", "extract", "statistics", "statistic", "data", "numbers",
    "list all", "compare", "percentage", "figures", "how many", "chart",
    "breakdown", "metrics", "calculate", "calculation", "total", "subtotal",
    "sum", "add up", "invoice", "bill", "amount", "price", "cost", "tax",
    "discount", "balance", "due", "payment", "charges", "fees", "grand total",
}


def classify_intent(message: str) -> str:
    """
    Fast keyword-based intent classifier.
    Returns 'summary', 'analyst', or 'rag'.
    Used to set the expected agent in retrieval_meta so the UI can
    show which agent was selected before the response streams.
    """
    lower = message.lower()
    if any(k in lower for k in SUMMARY_KEYWORDS):
        return "summary"
    if any(k in lower for k in ANALYST_KEYWORDS):
        return "analyst"
    return "rag"


def create_team(context: str) -> Team:
    """
    Build an Agno Team with three specialist agents.
    Context (retrieved chunks) is injected into every agent's system message
    so whichever agent the orchestrator routes to has full access to the document.
    """
    rag_agent     = create_rag_agent(context)
    summary_agent = create_summary_agent(context)
    analyst_agent = create_analyst_agent(context)

    team = Team(
        name="Doc Intelligence Team",
        mode="route",
        model=GroqModel(id=ORCHESTRATOR_MODEL),
        members=[rag_agent, summary_agent, analyst_agent],
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        markdown=True,
        show_tool_calls=False,
    )
    return team
