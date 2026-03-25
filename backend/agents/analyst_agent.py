"""
Analyst Agent — CP07
Triggered when the user asks to extract tables, numbers, statistics,
comparisons, or structured data from the document.
"""

from agno.agent import Agent
from agno.models.groq import Groq as GroqModel

ANALYST_MODEL = "llama-3.3-70b-versatile"

ANALYST_INSTRUCTIONS = """
You are a precise data extraction and analysis specialist.

When asked to extract or analyse data:
1. Identify all numerical values, statistics, percentages, and dates in the context.
2. Reconstruct any tables as clean markdown tables.
3. List key entities: names, organisations, products, locations.
4. Highlight comparisons or trends mentioned in the data.
5. Flag any data that appears inconsistent or requires verification.

Always cite [Page X] for every extracted data point.
Return only what is in the document — never infer or extrapolate values.
Format output as structured markdown with clear section headers.
"""


def create_analyst_agent(context: str) -> Agent:
    return Agent(
        name="Analyst Agent",
        role="Extracts tables, statistics, and structured data from documents",
        model=GroqModel(id=ANALYST_MODEL),
        instructions=ANALYST_INSTRUCTIONS,
        system_message=(
            "DOCUMENT CONTEXT — extract data from ONLY this material:\n\n"
            + context
        ),
        markdown=True,
        stream=True,
    )
