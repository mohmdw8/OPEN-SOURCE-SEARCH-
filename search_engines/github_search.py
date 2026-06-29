import requests

from core.config import TIMEOUTS, GITHUB_TOKEN


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


import datetime


def search_github(query: str, prog_lang: str = "Any", max_results: int = 8) -> list:
    try:
        q = query
        if prog_lang and prog_lang.lower() not in ("any", ""):
            q += f" language:{prog_lang}"
        cutoff = (datetime.date.today() - datetime.timedelta(days=730)).isoformat()
        q += f" pushed:>{cutoff} fork:false"
        params = {"q": q, "sort": "stars", "order": "desc", "per_page": max_results}
        r = requests.get(
            "https://api.github.com/search/repositories",
            params=params,
            headers=_github_headers(),
            timeout=TIMEOUTS["api_main"],
        )
        if r.status_code == 403:
            return []
        if r.status_code != 200:
            return []
        results = []
        for item in r.json().get("items", []):
            results.append({
                "title": item["full_name"],
                "href": item["html_url"],
                "body": item.get("description", "") or "",
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "usage": item.get("watchers_count", 0),
                "usage_label": "watchers",
                "language": item.get("language") or "N/A",
                "license": (item.get("license") or {}).get("spdx_id", "Unknown"),
                "updated": item.get("pushed_at", "")[:10],
                "open_issues": item.get("open_issues_count", 0),
                "archived": item.get("archived", False),
                "platform": "GitHub",
                "_from_api": True,
            })
        return results
    except Exception:
        return []


def fetch_readme(repo_full: str) -> str:
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo_full}/readme",
            headers=_github_headers(),
            timeout=TIMEOUTS["api_main"],
        )
        if r.status_code == 200:
            import base64
            content = r.json().get("content", "")
            return base64.b64decode(content).decode("utf-8", errors="ignore")
    except Exception:
        pass
    return ""


def fetch_repo_info(repo_full: str) -> dict | None:
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo_full}",
            headers=_github_headers(),
            timeout=TIMEOUTS["api_main"],
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None
