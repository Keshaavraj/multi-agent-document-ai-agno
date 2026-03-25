"""
Summary Agent — CP07
Triggered when the user asks for an overview, summary, or key points.
Produces a structured executive summary from the retrieved context.
"""

from agno.agent import Agent
from agno.models.groq import Groq as GroqModel

SUMMARY_MODEL = "llama-3.3-70b-versatile"

SUMMARY_INSTRUCTIONS = """
You are a professional document summarisation specialist.

When asked to summarise a document:
1. Start with a one-sentence purpose statement: what the document is about.
2. List 4–6 key takeaways as bullet points.
3. Identify any notable sections, chapters, or topics covered.
4. Note any important figures, dates, or names mentioned.
5. End with a "Bottom Line" — one sentence capturing the most important point.

Format clearly with headers. Be concise — no padding or repetition.
Always base your summary strictly on the provided document context.
"""


def create_summary_agent(context: str) -> Agent:
    return Agent(
        name="Summary Agent",
        role="Produces structured document summaries and executive overviews",
        model=GroqModel(id=SUMMARY_MODEL),
        instructions=SUMMARY_INSTRUCTIONS,
        system_message=(
            "DOCUMENT CONTEXT — summarise using ONLY this material:\n\n"
            + context
        ),
        markdown=True,
        stream=True,
    )
