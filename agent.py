"""
agent.py — Gemini-powered chat agent with manual function calling.

Uses the modern ``google.genai`` SDK (NOT the deprecated ``google.generativeai``).

This module implements a *manual* function-calling loop: the agent receives a
user message, the model may return a function-call request, and we route it
to the actual Python tool ourselves.  This is an intentional architectural
choice for explainability (judges can see every step).  We explicitly disable
the SDK's automatic function calling via
``AutomaticFunctionCallingConfig(disable=True)``.

The agent maintains a persistent chat session so follow-up questions retain
conversation context.  When the underlying data changes (new upload), the
caller should call ``reset_chat()`` to start fresh.

Usage:
    agent = BusinessAgent(api_key="...")
    response = agent.process_message(user_text, df, detected)
    # ... later ...
    response = agent.process_message(follow_up_text, df, detected)  # has memory
    agent.reset_chat()  # when data changes
"""

from google import genai
from google.genai import types

import pandas as pd
from typing import Callable

from tools import (
    compare_periods,
    generate_insight,
    get_sales_summary,
    get_top_products,
)


# ---------------------------------------------------------------------------
# Tool definitions (google.genai.types format)
# ---------------------------------------------------------------------------

def _build_function_declarations() -> list[types.FunctionDeclaration]:
    """Build the list of FunctionDeclaration objects that define the tools
    Gemini can call.  We use explicit declarations (not auto-introspection)
    because our actual Python tool functions accept internal parameters
    (df, detected column names) that should not be exposed to the model."""
    return [
        types.FunctionDeclaration(
            name="get_sales_summary",
            description=(
                "Get overall sales statistics for the uploaded dataset: "
                "total sales (RM), transaction count, average order value, "
                "and date range. No parameters needed."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="get_top_products",
            description=(
                "Get the top N products or items by total sales amount. "
                "Returns product name, total sales, and percentage of overall sales."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "n": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of top products to return (default 10).",
                    ),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="compare_periods",
            description=(
                "Compare sales performance between two date periods. "
                "Provide start and end dates for each period in YYYY-MM-DD format. "
                "Returns sales totals, transaction counts, averages, and percentage change."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "period_a_start": types.Schema(
                        type=types.Type.STRING,
                        description="Start date of first period in YYYY-MM-DD format (e.g., '2024-01-01').",
                    ),
                    "period_a_end": types.Schema(
                        type=types.Type.STRING,
                        description="End date of first period in YYYY-MM-DD format (inclusive).",
                    ),
                    "period_b_start": types.Schema(
                        type=types.Type.STRING,
                        description="Start date of second period in YYYY-MM-DD format (e.g., '2024-02-01').",
                    ),
                    "period_b_end": types.Schema(
                        type=types.Type.STRING,
                        description="End date of second period in YYYY-MM-DD format (inclusive).",
                    ),
                },
                required=["period_a_start", "period_a_end", "period_b_start", "period_b_end"],
            ),
        ),
        types.FunctionDeclaration(
            name="generate_insight",
            description=(
                "Analyse the dataset and generate data-driven business insights "
                "and recommendations. No parameters needed. Returns overview stats, "
                "trend direction, top products, category breakdown, and "
                "actionable recommendations."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        ),
    ]


def _build_system_prompt() -> str:
    """Build the system prompt that constrains the agent to the uploaded data."""
    return (
        "You are **Perniagaan Pintar** / **Business Insight Agent**, an AI assistant "
        "for Malaysian small business owners. You help analyse their uploaded sales data.\n\n"
        "## CRITICAL RULES (You MUST follow these):\n\n"
        "1. **DATA-BOUND**: Only discuss data from the uploaded dataset. NEVER make up or "
        "hallucinate numbers, dates, or products. If you don't have the data to answer a "
        "question, say so clearly.\n"
        "2. **LANGUAGE MATCH**: Always respond in the SAME language the user wrote in — "
        "English or Bahasa Melayu. If they mix languages, use the dominant one.\n"
        "3. **TOOLS FIRST**: Always use the available tools to get real data before "
        "answering. Never guess or approximate statistics.\n"
        "4. **BE CONCISE**: Malaysian business owners are busy. Give clear, actionable "
        "answers without unnecessary fluff. Use short paragraphs.\n"
        "5. **BE HELPFUL**: Provide context to numbers (e.g., 'This is a 15% increase'). "
        "Suggest what other questions they might ask.\n"
        "6. **MALAYSIAN CONTEXT**: Use 'RM' for Malaysian Ringgit. Reference local "
        "business context when relevant.\n\n"
        "## Available Tools\n\n"
        "- `get_sales_summary()` — Get overall sales stats: total sales, transaction "
        "count, average order value, date range.\n"
        "- `get_top_products(n=10)` — Get the top N products/items by sales amount.\n"
        "- `compare_periods(period_a_start, period_a_end, period_b_start, period_b_end)` "
        "— Compare sales between two date periods. Convert period descriptions like "
        "'last month' or 'this week' to YYYY-MM-DD format based on the actual data range.\n"
        "- `generate_insight()` — Get data-driven business insights and recommendations.\n\n"
        "## Date Format Note\n\n"
        "When using compare_periods, convert any date references (e.g., 'last month', "
        "'this month', 'January') to YYYY-MM-DD format based on the available data range. "
        "Look at the overall date range from the data to determine appropriate periods.\n\n"
        "## Conversation Memory\n\n"
        "Remember what was discussed earlier in this conversation so you can answer "
        "follow-up questions naturally."
    )


# ---------------------------------------------------------------------------
# BusinessAgent class
# ---------------------------------------------------------------------------

class BusinessAgent:
    """A Gemini-powered chat agent with manual function calling.

    The agent maintains a persistent ChatSession so follow-up questions retain
    context.  Call ``reset_chat()`` when the underlying data changes.

    Processing flow per turn:
    1. Send the user message to the persistent chat
    2. If Gemini requests a function call, execute the real Python function
    3. Send the result back to Gemini
    4. Return Gemini's final natural-language response
    """

    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash"):
        self._client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self._chat = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_message(
        self,
        user_message: str,
        df: pd.DataFrame,
        detected: dict,
    ) -> str:
        """Process a user message and return the assistant's final text response.

        The chat session persists across calls so the agent remembers context.
        """
        if not user_message or not user_message.strip():
            return ""

        # Lazy-init the chat session (persistent for multi-turn memory)
        if self._chat is None:
            self._chat = self._client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction=_build_system_prompt(),
                    tools=[
                        types.Tool(
                            function_declarations=_build_function_declarations()
                        ),
                    ],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )

        # Send user message to the persistent chat
        response = self._chat.send_message(user_message.strip())

        # Handle potential function calls recursively
        final_text = self._handle_response(response, df, detected)
        return final_text

    def reset_chat(self):
        """Reset the conversation.  Call this when data changes."""
        self._chat = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_response(self, response, df: pd.DataFrame, detected: dict) -> str:
        """Process a model response, executing any function calls recursively.

        This is the core of *manual* function calling — we inspect
        ``response.function_calls``, route each to the real Python tool, and
        feed the results back to the model until we get a text response.
        """
        if response.function_calls:
            # Collect all function responses
            parts = []
            for fc in response.function_calls:
                try:
                    tool_result = self._execute_tool(
                        fc.name, dict(fc.args), df, detected
                    )
                except Exception as exc:
                    tool_result = {"error": f"Failed to execute {fc.name}: {str(exc)}"}

                parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": tool_result},
                    )
                )

            # Send ALL function responses back at once in a single turn.
            # NOTE: google-genai >= 2.0 changed ``Chat.send_message`` to accept
            # a list of parts (``Union[list[PartUnionDict], PartUnionDict]``)
            # instead of a ``types.Content`` wrapper, so pass the parts list
            # directly.
            response = self._chat.send_message(parts)

            # Recurse to handle the model's follow-up response
            return self._handle_response(response, df, detected)

        # No function calls — return the text response
        return response.text

    def _execute_tool(self, name: str, args: dict, df: pd.DataFrame, detected: dict):
        """Route a function call to the corresponding Python tool function."""
        date_col = detected.get("date_col")
        amount_col = detected.get("amount_col")
        product_col = detected.get("product_col")
        category_col = detected.get("category_col")

        tool_map: dict[str, Callable] = {
            "get_sales_summary": lambda: get_sales_summary(
                df, amount_col=amount_col, date_col=date_col
            ),
            "get_top_products": lambda: get_top_products(
                df,
                product_col=product_col,
                amount_col=amount_col,
                n=args.get("n", 10),
            ),
            "compare_periods": lambda: compare_periods(
                df,
                date_col=date_col,
                amount_col=amount_col,
                period_a_start=args.get("period_a_start", ""),
                period_a_end=args.get("period_a_end", ""),
                period_b_start=args.get("period_b_start", ""),
                period_b_end=args.get("period_b_end", ""),
            ),
            "generate_insight": lambda: generate_insight(
                df,
                amount_col=amount_col,
                date_col=date_col,
                product_col=product_col,
                category_col=category_col,
            ),
        }

        tool_fn = tool_map.get(name)
        if tool_fn is None:
            return {"error": f"Unknown tool: '{name}'."}

        return tool_fn()
