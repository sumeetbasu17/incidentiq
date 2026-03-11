"""
IncidentIQ - Web Search Tool
Searches Stack Overflow, GitHub Issues, official docs, and tech blogs
for error resolutions using Tavily (primary) and Serper (fallback).
"""

import os
import json
import requests
from typing import Optional
from langchain_core.tools import tool
from config import Config


def search_tavily(query: str, max_results: int = 5) -> list:
    """Search using Tavily API - optimized for technical content."""
    if not Config.TAVILY_API_KEY:
        return []

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=Config.TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=[
                "stackoverflow.com",
                "github.com",
                "docs.python.org",
                "docs.oracle.com",
                "developer.mozilla.org",
                "learn.microsoft.com",
                "cloud.google.com",
                "aws.amazon.com",
                "medium.com",
                "dev.to",
            ],
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],
                "score": r.get("score", 0),
                "source": "tavily",
            })
        return results
    except Exception as e:
        print(f"Tavily search error: {e}")
        return []


def search_serper(query: str, max_results: int = 5) -> list:
    """Search using Serper API - Google search results."""
    if not Config.SERPER_API_KEY:
        return []

    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": Config.SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "num": max_results,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()

        results = []
        for r in data.get("organic", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "content": r.get("snippet", ""),
                "score": 1.0 - (len(results) * 0.1),
                "source": "serper",
            })
        return results
    except Exception as e:
        print(f"Serper search error: {e}")
        return []


@tool
def search_web(query: str) -> str:
    """
    Search the web for technical solutions, Stack Overflow answers, GitHub issues,
    and documentation related to an error or incident.
    
    Use this to find solutions for specific error messages, known bugs in libraries,
    configuration issues, and community-discussed problems.
    
    Args:
        query: A focused search query about the error or technical issue.
               Best format: "ErrorType specific message framework_name"
               Example: "ConnectionError pool exhausted PostgreSQL SQLAlchemy"
    """
    # Search both sources for comprehensive coverage
    tavily_results = search_tavily(query, max_results=4)
    serper_results = search_serper(query, max_results=3)

    # Combine and deduplicate by URL
    seen_urls = set()
    combined = []
    for r in tavily_results + serper_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            combined.append(r)

    if not combined:
        return json.dumps({
            "status": "no_results",
            "message": "No web results found. Try a different search query with more specific error details.",
            "query": query,
        })

    # Sort by relevance score
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)

    output = {
        "status": "success",
        "query": query,
        "total_results": len(combined),
        "results": combined[:6],
    }

    return json.dumps(output, indent=2)


@tool
def search_stackoverflow(query: str) -> str:
    """
    Search specifically on Stack Overflow for solutions to a programming error.
    
    Use this when you need community-vetted answers for specific error messages,
    exception types, or programming problems.
    
    Args:
        query: The error type and message to search for.
               Example: "NullPointerException HashMap concurrent access Java"
    """
    so_query = f"site:stackoverflow.com {query}"
    results = search_serper(so_query, max_results=5)

    if not results:
        results = search_tavily(f"stackoverflow {query}", max_results=5)

    if not results:
        return json.dumps({
            "status": "no_results",
            "message": "No Stack Overflow results found. Try simplifying the search query.",
            "query": query,
        })

    output = {
        "status": "success",
        "query": query,
        "platform": "Stack Overflow",
        "results": results[:5],
    }

    return json.dumps(output, indent=2)
