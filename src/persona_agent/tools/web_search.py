"""Web search tool for searching the internet.

This module provides web search capabilities using various search providers.
It includes a mock implementation for testing and can be extended with
real search APIs like Google Custom Search, Bing Search, etc.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from persona_agent.tools.base import (
    Tool,
    ToolCategory,
    ToolContext,
    ToolResult,
    ToolRiskLevel,
    ToolSchema,
)

logger = logging.getLogger(__name__)


class SearchProvider:
    """Base class for search providers."""

    async def search(self, query: str, num_results: int = 5) -> dict[str, Any]:
        """Execute search query.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            Search results dictionary
        """
        raise NotImplementedError


class MockSearchProvider(SearchProvider):
    """Mock search provider for testing."""

    def __init__(self):
        self.mock_data: dict[str, list[dict]] = {
            "python": [
                {"title": "Python Programming Language", "url": "https://python.org", "snippet": "The official home of the Python Programming Language."},
                {"title": "Python Tutorial - W3Schools", "url": "https://w3schools.com/python", "snippet": "Learn Python with our comprehensive tutorial."},
            ],
            "default": [
                {"title": f"Result {i}", "url": f"https://example.com/result{i}", "snippet": f"This is a mock search result {i} for testing purposes."}
                for i in range(1, 6)
            ],
        }

    async def search(self, query: str, num_results: int = 5) -> dict[str, Any]:
        """Return mock search results."""
        query_lower = query.lower()

        # Find matching mock data
        results = self.mock_data.get("default", [])
        for key, data in self.mock_data.items():
            if key in query_lower:
                results = data
                break

        return {
            "query": query,
            "total_results": len(results),
            "results": results[:num_results],
            "source": "mock",
        }


class SerperSearchProvider(SearchProvider):
    """Search provider using Serper.dev API (Google Search)."""

    API_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        if not self.api_key:
            logger.warning("Serper API key not provided, search will fail")

    async def search(self, query: str, num_results: int = 5) -> dict[str, Any]:
        """Execute search using Serper API."""
        if not self.api_key:
            return {
                "query": query,
                "error": "Serper API key not configured",
                "results": [],
            }

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "q": query,
            "num": min(num_results, 10),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                # Extract organic results
                organic_results = data.get("organic", [])
                results = [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("link", ""),
                        "snippet": r.get("snippet", ""),
                    }
                    for r in organic_results[:num_results]
                ]

                return {
                    "query": query,
                    "total_results": data.get("searchInformation", {}).get("totalResults", 0),
                    "results": results,
                    "source": "serper",
                }

        except httpx.HTTPError as e:
            logger.error(f"Serper API error: {e}")
            return {
                "query": query,
                "error": f"API error: {e}",
                "results": [],
            }
        except Exception as e:
            logger.error(f"Unexpected error in Serper search: {e}")
            return {
                "query": query,
                "error": f"Search failed: {e}",
                "results": [],
            }


class DuckDuckGoSearchProvider(SearchProvider):
    """Search provider using DuckDuckGo (no API key required)."""

    API_URL = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, num_results: int = 5) -> dict[str, Any]:
        """Execute search using DuckDuckGo.

        Note: This uses the HTML interface which may break if DDG changes their layout.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.API_URL,
                    data={"q": query, "kl": "us-en"},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                )
                response.raise_for_status()

                # Parse HTML (simple parsing)
                html = response.text
                results = []

                # Extract results from HTML
                import re
                result_blocks = re.findall(
                    r'<div class="result__body">(.*?)</div>\s*</div>',
                    html,
                    re.DOTALL,
                )

                for block in result_blocks[:num_results]:
                    # Extract title and URL
                    title_match = re.search(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', block)
                    url_match = re.search(r'href="([^"]*)"', block)
                    snippet_match = re.search(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', block)

                    if title_match and url_match:
                        title = re.sub(r'<[^>]+>', '', title_match.group(1))
                        url = url_match.group(1)
                        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)) if snippet_match else ""

                        # DuckDuckGo uses redirects, extract actual URL
                        if url.startswith("//duckduckgo.com/l/?"):
                            uddg_match = re.search(r'uddg=([^&]+)', url)
                            if uddg_match:
                                import urllib.parse
                                url = urllib.parse.unquote(uddg_match.group(1))

                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                        })

                return {
                    "query": query,
                    "total_results": len(results),
                    "results": results,
                    "source": "duckduckgo",
                }

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return {
                "query": query,
                "error": f"Search failed: {e}",
                "results": [],
            }


class WebSearchTool(Tool):
    """Tool for searching the web.

    Supports multiple search providers:
    - mock: For testing (default)
    - serper: Serper.dev API (requires API key)
    - duckduckgo: DuckDuckGo (no API key, may be less reliable)
    """

    name = "web_search"
    description = "Search the web for information"

    PROVIDERS = {
        "mock": MockSearchProvider,
        "serper": SerperSearchProvider,
        "duckduckgo": DuckDuckGoSearchProvider,
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider_name = (config or {}).get("provider", "mock")
        self.provider = self._create_provider()

    def _create_provider(self) -> SearchProvider:
        """Create the configured search provider."""
        provider_class = self.PROVIDERS.get(self.provider_name, MockSearchProvider)
        return provider_class()

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-10)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            required=["query"],
            category=ToolCategory.NETWORK,
            risk_level=ToolRiskLevel.HIGH,
            examples=[
                {"query": "Python programming tutorials"},
                {"query": "latest AI developments", "num_results": 3},
            ],
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        query = params["query"]
        num_results = min(params.get("num_results", 5), 10)

        # Validate query
        if not query or len(query) > 500:
            return ToolResult.error_result(
                "Query must be between 1 and 500 characters"
            )

        # Execute search
        try:
            result = await self.provider.search(query, num_results)

            if "error" in result:
                return ToolResult.error_result(result["error"])

            return ToolResult.success_result(result)

        except Exception as e:
            logger.exception("Web search failed")
            return ToolResult.error_result(f"Search failed: {e}")
