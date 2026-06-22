from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass
class WebSearchHit:
    title: str
    url: str
    snippet: str | None = None
    domain: str | None = None


class WebSearchClient:
    def __init__(self, timeout_seconds: float = 20) -> None:
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, max_results: int = 8) -> list[WebSearchHit]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; NOVAIONSiteHunter/1.0; +https://novaion.ai)",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        hits: list[WebSearchHit] = []
        for result in soup.select(".result")[: max_results * 2]:
            link = result.select_one(".result__a")
            if not link:
                continue
            title = link.get_text(" ", strip=True)
            href = self._clean_url(link.get("href") or "")
            snippet_node = result.select_one(".result__snippet")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None
            if not title or not href:
                continue
            domain = urlparse(href).netloc.lower().removeprefix("www.")
            hits.append(WebSearchHit(title=title, url=href, snippet=snippet, domain=domain))
            if len(hits) >= max_results:
                break
        return hits

    def _clean_url(self, href: str) -> str:
        if href.startswith("//"):
            href = f"https:{href}"
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        if "uddg" in query and query["uddg"]:
            return unquote(query["uddg"][0])
        return href


def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")
