"""
Chart Agent
Extracts numerical data from documents and returns a structured chart
specification that the frontend renders using Recharts.
"""

from agno.agent import Agent
from agno.models.groq import Groq as GroqModel

CHART_MODEL = "llama-3.3-70b-versatile"

CHART_INSTRUCTIONS = """
You are a data visualization specialist. You extract numerical data from documents
and return both a text summary AND a chart specification the UI can render.

STRICT RULES:
- Extract ONLY numbers explicitly stated in the document context.
- NEVER invent or estimate data values.
- If there is no numerical data, say: "No chartable data found in this document."
- Cite every data point with [Page X].

── CHART SELECTION GUIDE ───────────────────────────────────────────────────────
- Bar chart   → comparing categories (sales by region, expenses by type, scores by item)
- Line chart  → trends over time (monthly revenue, price changes over dates)
- Pie chart   → proportions/percentages (budget breakdown, market share, expense split)

── OUTPUT FORMAT ───────────────────────────────────────────────────────────────

Always respond with TWO parts:

**Part 1 — Text summary** (brief, 2-4 lines explaining what the chart shows and key insight)

**Part 2 — Chart specification** (a ```chart code block with valid JSON):

For bar or line chart:
```chart
{
  "type": "bar",
  "title": "Chart Title Here",
  "xKey": "category",
  "yKey": "value",
  "yLabel": "Amount ($)",
  "data": [
    {"category": "Label A", "value": 1200},
    {"category": "Label B", "value": 3400}
  ]
}
```

For pie chart:
```chart
{
  "type": "pie",
  "title": "Chart Title Here",
  "data": [
    {"name": "Category A", "value": 45},
    {"name": "Category B", "value": 30},
    {"name": "Category C", "value": 25}
  ]
}
```

── RULES FOR THE JSON ──────────────────────────────────────────────────────────
- All values must be numbers (no currency symbols, no commas inside strings).
- Maximum 12 data points for readability.
- Use short, clear category labels (max 15 chars).
- The ```chart block must contain ONLY valid JSON — no comments, no extra text.
- If multiple chart types are useful, pick the most insightful one.
"""


def create_chart_agent(context: str) -> Agent:
    return Agent(
        name="Chart Agent",
        role="Extracts data and generates chart specifications for visualization",
        model=GroqModel(id=CHART_MODEL),
        instructions=CHART_INSTRUCTIONS,
        system_message=(
            "DOCUMENT CONTEXT — extract chartable data from ONLY this material:\n\n"
            + context
        ),
        markdown=True,
        stream=True,
    )
