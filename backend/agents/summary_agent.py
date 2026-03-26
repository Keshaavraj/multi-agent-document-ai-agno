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

STRICT RULE — document-only:
- Use ONLY the content present in the provided document context.
- Do NOT draw on general knowledge, training data, or outside information.
- Do NOT assume, infer, or add anything not explicitly stated in the document.
- If the document does not contain enough information to answer, say clearly:
  "I could not find sufficient content in the provided documents to answer this."

When summarising:
1. Start with a one-sentence purpose statement: what the document is about.
2. List 4–6 key takeaways as bullet points — only from the document.
3. Identify notable sections, chapters, or topics covered in the document.
4. Note important figures, dates, or names found in the document.
5. End with a "Bottom Line" — one sentence capturing the most important point from the document.

Format clearly with headers. Be concise — no padding or repetition.
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
