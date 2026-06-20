import sys
import re
import json
import time
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.align import Align
from rich.rule import Rule

from core.config import TIMEOUTS, PLATFORMS, LICENSE_MAP, UNKNOWN_LICENSE, QUESTIONARY_STYLE
from core.cache import lookup_cache, save_to_cache
from utils.translation import detect_language, translate_to_english, translate_text, LANGUAGE_NAMES, rtl_wrap
from ai_backend.llm_handler import ai_chat, safe_parse_ai_json
from ai_backend.ranking import ai_rank_results
from search_engines import (
    search_github, search_huggingface, search_pypi, search_npm,
    search_docker, search_ddg, fetch_readme, fetch_repo_info,
    smart_deduplicate, prefilter_results,
)

console = Console()

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "that", "this", "these", "those", "it", "its", "i", "me", "my",
    "we", "our", "you", "your", "he", "she", "they", "their", "them", "us",
    "for", "to", "of", "in", "on", "at", "by", "with", "from", "into", "like",
    "want", "find", "get", "use", "using", "help", "helps", "allow", "allows",
    "let", "lets", "give", "gives", "make", "makes", "look", "looking",
    "just", "very", "also", "really", "some", "any", "all", "more", "most",
    "much", "many", "than", "then", "when", "where", "which", "who", "how",
    "what", "why", "easy", "easily", "simple", "quickly", "fast", "tool",
    "program", "software", "application", "something", "need", "needs",
}

_TECH_MAP = {
    "website": "web", "websites": "web", "web": "web",
    "program": "app", "programming": "dev",
    "build": "builder", "create": "generator", "make": "builder",
    "fast": "performance", "data": "data",
    "database": "database", "store": "storage", "storage": "storage",
    "cloud": "cloud", "file": "file", "image": "image",
    "video": "video", "audio": "audio",
    "chat": "chat", "email": "email", "search": "search",
    "machine learning": "ml",
    "ai": "ai", "api": "api",
    "server": "server", "deploy": "deploy",
    "monitor": "monitor", "test": "test",
    "scrape": "scrape", "scraping": "scrape",
    "download": "downloader", "upload": "upload",
    "convert": "converter", "parse": "parser",
    "encrypt": "security", "backup": "backup",
    "sync": "sync", "task": "task", "schedule": "scheduler",
    "graph": "graph", "chart": "chart",
    "pdf": "pdf", "excel": "spreadsheet",
    "markdown": "markdown", "cli": "cli",
    "game": "game", "mobile": "mobile",
    "desktop": "gui", "docker": "docker",
    "kubernetes": "k8s",
    "penetration testing": "pentest",
    "wifi": "wifi",
    "wireless": "wireless",
    "password": "password",
    "vulnerability": "vulnerability",
    "scanning": "scanner",
    "sniffing": "sniffer",
    "forensics": "forensics",
    "reverse engineering": "reverse",
    "wpa": "wpa",
    "brute force": "brute-force",
    "osint": "osint",
    "recon": "recon",
}


def print_logo():
    console.print()
    lines = [
        " [bold bright_green] ██████╗ ██████╗ ███████╗[/]",
        " [bold bright_green]██╔═══██╗██╔══██╗██╔════╝[/]",
        " [bold bright_green]██║   ██║██████╔╝███████╗[/]",
        " [bold bright_green]██║   ██║██╔═══╝ ╚════██║[/]",
        " [bold bright_green]╚██████╔╝██║     ███████║[/]",
        " [bold bright_green] ╚═════╝ ╚═╝     ╚══════╝[/]",
    ]
    for line in lines:
        console.print(line)
    console.print(Text("  open source search", style="dim white"))
    console.print()
    console.print(Panel.fit(
        Align.center(Text("Hybrid search: Direct APIs + DDG fallback | AI query expansion + AI ranking", style="dim cyan")),
        border_style="bright_black",
        padding=(0, 2),
    ))
    console.print()


def _smart_fallback_query(translated: str) -> str:
    words = translated.lower().split()
    clean_words = []
    for w in words:
        clean_w = re.sub(r'[^a-z0-9]', '', w)
        if clean_w and clean_w not in _STOPWORDS:
            clean_words.append(clean_w)
    return " ".join(clean_words) if clean_words else translated


def expand_query(user_input: str) -> dict:
    cached_result = lookup_cache(user_input)
    if cached_result:
        console.print(
            f"  [green]Using cached result (Similarity match: {cached_result['_match_similarity']}%)[/]\n"
            f"  [dim]q1:[/] [white]{cached_result['en_query']}[/]"
        )
        return cached_result

    translated = user_input
    if detect_language(user_input) != "en":
        with Progress(SpinnerColumn(), TextColumn("[dim]Translating..."), transient=True) as p:
            p.add_task("", total=None)
            translated = translate_to_english(user_input)
        if translated != user_input:
            console.print(f"[dim]Translated:[/] [italic white]{translated}[/]")

    ai_prompt = f"""You are a world-class Software Architect and Search Engineer.
Your goal is to translate user descriptions into highly precise technical search terms.

User Request: "{translated}"

Instructions:
1. Detect if the user description contains MULTIPLE independent technical tasks or tools (e.g., "scraping and directory creation", "pdf parser and spreadsheet generator").
2. If multiple tasks are detected:
   - Break them down into distinct, individual search concepts and place them in the "sub_queries" array.
   - Example: "scrape web and make folders" -> "sub_queries": ["web scraper crawler", "directory creation filesystem automation"]
3. If it is a single unified task, "sub_queries" should contain just one main technical query.
4. Keep query1 and query2 extremely concise (max 3-4 words).

Return ONLY valid JSON:
{{
  "sub_queries": ["concept 1", "concept 2"],
  "query1": "primary unified search query (2-3 words)",
  "query2": "alternative technical synonyms (3-4 words)",
  "query3": "related package category (2-3 words)",
  "keywords": ["key1", "key2", "key3"],
  "language": "Any",
  "type": "any"
}}"""

    ai_raw = ai_chat(ai_prompt)
    parsed = safe_parse_ai_json(ai_raw, dict)

    if parsed:
        sub_queries = parsed.get("sub_queries", [])
        q1 = parsed.get("query1", "").strip()
        q2 = parsed.get("query2", "").strip()
        q3 = parsed.get("query3", "").strip()

        if q1 and detect_language(q1) == "en":
            if not sub_queries:
                sub_queries = [q1]

            console.print(
                f"  [dim]Sub-queries detected:[/] [cyan]{', '.join(sub_queries)}[/]\n"
                f"  [dim]q1:[/] [white]{q1}[/]\n"
                f"  [dim]q2:[/] [white]{q2}[/]\n"
                f"  [dim]q3:[/] [white]{q3}[/]"
            )
            result_dict = {
                "sub_queries": sub_queries,
                "en_query": q1,
                "alt_queries": [x for x in [q2, q3] if x and detect_language(x) == "en"],
                "keywords": parsed.get("keywords", translated.split()[:5]),
                "language": parsed.get("language", "Any"),
                "type": parsed.get("type", "any"),
                "original": user_input,
                "translated": translated,
            }
            save_to_cache(result_dict)
            return result_dict

    fallback_query = _smart_fallback_query(translated)
    console.print(f"  [dim]fallback query:[/] [white]{fallback_query}[/]")
    return {
        "sub_queries": [fallback_query],
        "en_query": fallback_query,
        "alt_queries": [],
        "keywords": fallback_query.split()[:5],
        "language": "Any",
        "type": "any",
        "original": user_input,
        "translated": translated,
    }


def search_all(query_info: dict, selected_platforms: list, max_per: int = 6) -> list:
    sub_queries = query_info.get("sub_queries", [])
    if not sub_queries:
        sub_queries = [query_info["en_query"]]

    primary_list = sub_queries
    if len(sub_queries) == 1:
        primary_list = sub_queries + query_info.get("alt_queries", [])

    lang = query_info.get("language", "Any")
    all_results = []
    MIN_API_RESULTS = 3
    MAX_TOTAL_WAIT = 25

    def _run_api(api_type, q, lang, name, domain, n):
        try:
            if api_type == "github":
                return search_github(q, lang, n)
            elif api_type == "huggingface":
                return search_huggingface(q, n)
            elif api_type == "pypi":
                return search_pypi(q, n)
            elif api_type == "npm":
                return search_npm(q, n)
            elif api_type == "docker":
                return search_docker(q, n)
            elif domain:
                return search_ddg(q, name, domain, n)
        except Exception:
            pass
        return []

    def _search_platform_for_query(name, q):
        info = PLATFORMS.get(name, {})
        api_type = info.get("api", "ddg")
        domain = info.get("domain", "")
        collected = []
        seen_hrefs = set()

        res = _run_api(api_type, q, lang, name, domain, max_per)
        for r in res:
            href = r.get("href", "")
            if href and href not in seen_hrefs:
                seen_hrefs.add(href)
                collected.append(r)

        if len(collected) < MIN_API_RESULTS and domain and api_type != "ddg":
            ddg = search_ddg(q, name, domain, max_per)
            for r in ddg:
                href = r.get("href", "")
                if href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    collected.append(r)
        return collected

    start = time.time()
    tasks = []
    for name in selected_platforms:
        for q in primary_list[:4]:
            tasks.append((name, q))

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_search_platform_for_query, name, q): (name, q) for name, q in tasks}
        for fut in as_completed(futures, timeout=MAX_TOTAL_WAIT):
            try:
                all_results.extend(fut.result())
            except Exception:
                pass
            if time.time() - start > MAX_TOTAL_WAIT * 0.8 and len(all_results) > 15:
                break

    return smart_deduplicate(all_results)


def display_results_table(results: list):
    table = Table(
        box=box.ROUNDED,
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=True,
        expand=True,
    )
    table.add_column("#", style="dim", width=3, no_wrap=True)
    table.add_column("Project", style="bold white", min_width=20)
    table.add_column("Platform", style="cyan", width=11, no_wrap=True)
    table.add_column("Stars", style="yellow", width=10, no_wrap=True)
    table.add_column("Usage", style="bright_yellow", width=14, no_wrap=True)
    table.add_column("Match%", style="bright_green", width=8, no_wrap=True)
    table.add_column("License", style="magenta", width=11, no_wrap=True)
    table.add_column("Language", style="blue", width=11, no_wrap=True)
    table.add_column("Description", style="dim white", min_width=22)

    for i, r in enumerate(results, 1):
        stars = r.get("stars", 0) or 0
        usage = r.get("usage", 0) or 0
        usage_label = r.get("usage_label", "")
        stars_str = f"{stars:,}" if stars else "\u2014"
        usage_str = f"{usage:,} {usage_label}" if usage else "\u2014"
        match_pct = r.get("_match_pct", "\u2014")
        match_str = f"{match_pct}%" if isinstance(match_pct, int) else "\u2014"
        table.add_row(
            str(i),
            r.get("title", ""),
            r.get("platform", ""),
            stars_str,
            usage_str,
            match_str,
            r.get("license", "Unknown") or "Unknown",
            r.get("language", "N/A") or "N/A",
            (r.get("body", "") or "")[:75],
        )
    console.print(table)


def action_open_browser(url: str):
    try:
        subprocess.Popen(["xdg-open", url], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        console.print(f"[green]Opening:[/] {url}")
    except Exception:
        console.print(f"[yellow]URL:[/] {url}")


def action_summary(result: dict):
    title = result.get("title", "")
    desc = result.get("body", "") or ""
    url = result.get("href", "")
    platform = result.get("platform", "")
    language = result.get("language", "") or ""
    stars = result.get("stars", 0) or 0
    usage = result.get("usage", 0) or 0
    usage_lbl = result.get("usage_label", "")
    license_ = result.get("license", "") or ""
    updated = result.get("updated", "") or ""

    readme = ""
    if "github.com" in url:
        parts = url.replace("https://github.com/", "").strip("/").split("/")
        if len(parts) >= 2:
            readme = fetch_readme("/".join(parts[:2]))[:3000]

    context_parts = []
    if language and language not in ("N/A", "Model", "Docker"):
        context_parts.append(f"written in {language}")
    if stars > 0:
        context_parts.append(f"{stars:,} GitHub stars")
    if usage > 0 and usage_lbl:
        context_parts.append(f"{usage:,} {usage_lbl}")
    if license_:
        context_parts.append(f"licensed under {license_}")
    if updated:
        context_parts.append(f"last updated {updated}")
    context_str = ", ".join(context_parts) if context_parts else "details unknown"

    proj_type = result.get("type", "") or ""
    if language == "Model" or platform == "Hugging Face":
        angle = "Focus on: what ML task it solves, model architecture if known, dataset it was trained on, and how to use it."
    elif "cli" in proj_type.lower() or "tool" in proj_type.lower():
        angle = "Focus on: what problem it solves, key commands or workflows, who benefits most, and any important limitations."
    elif "library" in proj_type.lower() or "framework" in proj_type.lower():
        angle = "Focus on: what it helps developers build, its API style, ecosystem fit, and who should use it."
    else:
        angle = "Focus on: what it does, main features, who it is for, and any notable highlights or limitations."

    prompt = f"""You are a technical writer summarizing open-source projects for developers.

Project: {title}
Platform: {platform}
Context: {context_str}
Description: {desc}
README excerpt:
{readme}

Write a clear, concise summary in 5-7 sentences. {angle}
Be specific \u2014 mention actual feature names, commands, or integrations visible in the README.
Do not repeat the project name more than once. Write in plain English."""

    with Progress(SpinnerColumn(), TextColumn("[cyan]Generating summary..."), transient=True) as p:
        p.add_task("", total=None)
        answer = ai_chat(prompt)

    if not answer:
        console.print("[red]Could not generate summary.[/]")
        return

    console.print(Panel(answer, title=f"[bold cyan]Summary \u2014 {title}[/]", border_style="cyan"))

    console.print()
    want_translate = questionary.confirm(
        "Translate this summary to another language?",
        default=False,
        style=QUESTIONARY_STYLE,
    ).ask()

    if want_translate:
        target_lang = questionary.select(
            "Translate to:",
            choices=LANGUAGE_NAMES,
            style=QUESTIONARY_STYLE,
        ).ask()
        if target_lang:
            with Progress(SpinnerColumn(), TextColumn("[cyan]Translating..."), transient=True) as p:
                p.add_task("", total=None)
                translated_summary = translate_text(answer, target_lang)
            if translated_summary and translated_summary != answer:
                console.print(Panel(
                    rtl_wrap(translated_summary),
                    title=f"[bold magenta]Summary \u2014 {title} ({target_lang})[/]",
                    border_style="magenta",
                ))


def action_usage(result: dict):
    title = result.get("title", "")
    desc = result.get("body", "") or ""
    url = result.get("href", "")
    platform = result.get("platform", "")
    language = result.get("language", "") or ""
    stars = result.get("stars", 0) or 0
    license_ = result.get("license", "") or ""

    readme = ""
    if "github.com" in url:
        parts = url.replace("https://github.com/", "").strip("/").split("/")
        if len(parts) >= 2:
            readme = fetch_readme("/".join(parts[:2]))[:3000]

    if platform == "PyPI" or language == "Python":
        install_hint = "Installation is likely via pip. Show: pip install or pip3 install."
    elif platform == "npm" or language == "JavaScript":
        install_hint = "Installation via npm or yarn. Show both if applicable."
    elif platform == "Docker Hub" or language == "Docker":
        install_hint = "Show docker pull and docker run commands with common options."
    elif platform == "Hugging Face" or language == "Model":
        install_hint = "Show how to load the model with transformers or the relevant library."
    elif language == "Go":
        install_hint = "Show go install command."
    elif language == "Rust":
        install_hint = "Show cargo install command."
    else:
        install_hint = "Show the most common installation method for this platform."

    maturity = ""
    if stars > 10000:
        maturity = "This is a well-established project with extensive documentation."
    elif stars > 1000:
        maturity = "This is a moderately popular project."
    else:
        maturity = "This may be a newer or niche project."

    prompt = f"""You are a senior developer writing a quick-start guide.

Project: {title}
Platform: {platform}
Language: {language}
License: {license_}
Description: {desc}
{maturity}
{install_hint}

README:
{readme}

Return ONLY a JSON array of 3-6 steps. Each step:
  "step":    short action label (Install / Configure / Basic usage / Example / etc.)
  "command": exact single-line shell or code command
  "note":    1-2 sentences explaining what this does

Extract commands directly from the README when available.
Return ONLY valid JSON array, no markdown, no extra text."""

    with Progress(SpinnerColumn(), TextColumn("[cyan]Fetching usage info..."), transient=True) as p:
        p.add_task("", total=None)
        answer = ai_chat(prompt)

    steps = safe_parse_ai_json(answer, list) if answer else None

    if steps:
        console.print()
        console.print(Rule(f"[bold yellow]Usage \u2014 {title}[/]", style="yellow"))
        for s in steps:
            console.print(f"\n[bold cyan]{s.get('step', 'Step')}[/]")
            if s.get("note"):
                console.print(f"  [dim]{s['note']}[/]")
            if s.get("command"):
                console.print(Panel(
                    f"[bold bright_green]{s['command']}[/]",
                    border_style="green",
                    padding=(0, 2),
                ))
        console.print()
    else:
        if answer:
            console.print(Panel(answer, title=f"[bold yellow]Usage \u2014 {title}[/]", border_style="yellow"))
        else:
            console.print("[red]Could not fetch usage info.[/]")


def action_translate_description(result: dict):
    desc = result.get("body", "") or result.get("title", "")
    if not desc:
        console.print("[red]No description to translate.[/]")
        return
    target_lang = questionary.select(
        "Translate description to:",
        choices=LANGUAGE_NAMES,
        style=QUESTIONARY_STYLE,
    ).ask()
    if not target_lang:
        return
    with Progress(SpinnerColumn(), TextColumn("[cyan]Translating..."), transient=True) as p:
        p.add_task("", total=None)
        translated = translate_text(desc, target_lang)
    if translated:
        console.print(Panel(rtl_wrap(translated), title=f"[bold magenta]Translation ({target_lang})[/]", border_style="magenta"))
    else:
        console.print("[red]Translation failed.[/]")


def action_license_info(result: dict):
    lic_raw = (result.get("license", "") or "").lower().strip()
    info = LICENSE_MAP.get(lic_raw, UNKNOWN_LICENSE)
    t = Table(box=box.SIMPLE, border_style="bright_black", show_header=False)
    t.add_column("Field", style="bold cyan", width=14)
    t.add_column("Value", style="white")
    t.add_row("License", info["name"])
    t.add_row("Allowed", info["allowed"])
    t.add_row("Forbidden", info["forbidden"])
    t.add_row("Conditions", info["conditions"])
    console.print(Panel(t, title="[bold magenta]License Info[/]", border_style="magenta"))


def action_clone_command(result: dict):
    url = result.get("href", "")
    if "github.com" in url or "gitlab.com" in url or "codeberg.org" in url:
        cmd = f"git clone {url}.git"
    else:
        cmd = f"# Visit: {url}"
    console.print(Panel(f"[bold green]{cmd}[/]", title="Clone Command", border_style="green"))


def action_similar_search(result: dict, selected_platforms: list):
    desc = result.get("body", "") or result.get("title", "")
    console.print(f"\n[cyan]Searching for projects similar to:[/] {result.get('title', '')}")
    q_info = expand_query(desc)
    with Progress(SpinnerColumn(), TextColumn("[cyan]Searching..."), transient=True) as p:
        p.add_task("", total=None)
        results = search_all(q_info, selected_platforms)
    if not results:
        console.print("[red]No results found.[/]")
        return
    results = prefilter_results(results, q_info.get("keywords", []))
    with Progress(SpinnerColumn(), TextColumn("[cyan]AI ranking..."), transient=True) as p:
        p.add_task("", total=None)
        results = ai_rank_results(results, desc)
    display_results_table(results)
    handle_result_selection(results, selected_platforms)


def compare_projects():
    console.print("[cyan]Enter 2-4 project URLs or names to compare (empty line to finish):[/]")
    entries = []
    while len(entries) < 4:
        line = questionary.text(
            f"Project {len(entries) + 1} (URL or name):",
            style=QUESTIONARY_STYLE,
        ).ask()
        if not line:
            break
        entries.append(line.strip())
    if len(entries) < 2:
        console.print("[red]Need at least 2 projects to compare.[/]")
        return

    projects = []
    for entry in entries:
        if entry.startswith("http"):
            parsed = urlparse(entry)
            path_parts = parsed.path.strip("/").split("/")
            p = {
                "title": "/".join(path_parts[:2]), "href": entry,
                "body": "", "stars": 0, "forks": 0,
                "language": "N/A", "license": "Unknown",
                "platform": parsed.netloc, "features": "",
            }
            if "github.com" in parsed.netloc and len(path_parts) >= 2:
                repo = "/".join(path_parts[:2])
                info = fetch_repo_info(repo)
                if info:
                    p.update({
                        "title": info.get("full_name", p["title"]),
                        "body": info.get("description", "") or "",
                        "stars": info.get("stargazers_count", 0),
                        "forks": info.get("forks_count", 0),
                        "language": info.get("language") or "N/A",
                        "license": (info.get("license") or {}).get("spdx_id", "Unknown"),
                    })
        else:
            p = {
                "title": entry, "href": "", "body": "",
                "stars": 0, "forks": 0, "language": "N/A",
                "license": "Unknown", "platform": "Unknown", "features": "",
            }
        projects.append(p)

    console.print("[dim]Fetching key features for each project...[/]")
    for p in projects:
        readme = ""
        if "github.com" in p.get("href", ""):
            parts = p["href"].replace("https://github.com/", "").strip("/").split("/")
            if len(parts) >= 2:
                readme = fetch_readme("/".join(parts[:2]))[:2000]

        feat_prompt = f"""List the 4-5 most important features of this open-source project.
Project: {p['title']}
Description: {p['body']}
README: {readme}

Return ONLY a JSON array of short feature strings, max 8 words each.
Example: ["Fast async processing", "Built-in REST API", "Docker support", "MIT license"]
Return ONLY valid JSON array, no extra text."""

        with Progress(SpinnerColumn(), TextColumn(f"[dim]Getting features: {p['title'][:25]}...[/]"), transient=True) as pr:
            pr.add_task("", total=None)
            feat_raw = ai_chat(feat_prompt)

        features = safe_parse_ai_json(feat_raw, list)
        if features and isinstance(features, list):
            p["features"] = "\n".join(f"\u2022 {f}" for f in features[:5] if isinstance(f, str))
        else:
            p["features"] = (p.get("body", "") or "")[:80] or "\u2014"

    t = Table(
        box=box.ROUNDED,
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=True,
    )
    t.add_column("Field", style="bold cyan", width=14)
    for p in projects:
        t.add_column(p["title"].split("/")[-1], style="white", min_width=18)

    for label, key in [
        ("Platform", "platform"), ("Stars", "stars"), ("Forks", "forks"),
        ("Language", "language"), ("License", "license"),
    ]:
        row = [label]
        for p in projects:
            val = p.get(key, "\u2014")
            if key in ("stars", "forks"):
                val = f"{val:,}" if isinstance(val, int) and val > 0 else "\u2014"
            row.append(str(val) if val else "\u2014")
        t.add_row(*row)

    features_row = ["Key Features"]
    for p in projects:
        features_row.append(p.get("features", "\u2014") or "\u2014")
    t.add_row(*features_row)

    console.print()
    console.print(Panel(t, title="[bold cyan]Project Comparison[/]", border_style="cyan"))

    ai_choice = questionary.confirm("Generate AI comparison summary?", style=QUESTIONARY_STYLE).ask()
    if ai_choice:
        prompt = f"""Compare these open-source projects concisely and technically.
Projects:
{json.dumps([{
    "name": p["title"], "description": p["body"],
    "stars": p["stars"], "language": p["language"],
    "license": p["license"], "features": p["features"],
} for p in projects], indent=2)}

Cover: main differences, strengths, weaknesses, and a clear recommendation for different use cases.
Write in plain English."""

        with Progress(SpinnerColumn(), TextColumn("[cyan]AI comparing..."), transient=True) as prog:
            prog.add_task("", total=None)
            answer = ai_chat(prompt)

        if answer:
            console.print(Panel(answer, title="[bold cyan]AI Comparison[/]", border_style="cyan"))

            console.print()
            want_translate = questionary.confirm(
                "Translate this comparison to another language?",
                default=False,
                style=QUESTIONARY_STYLE,
            ).ask()
            if want_translate:
                target_lang = questionary.select(
                    "Translate to:",
                    choices=LANGUAGE_NAMES,
                    style=QUESTIONARY_STYLE,
                ).ask()
                if target_lang:
                    with Progress(SpinnerColumn(), TextColumn("[cyan]Translating..."), transient=True) as p:
                        p.add_task("", total=None)
                        translated_cmp = translate_text(answer, target_lang)
                    if translated_cmp and translated_cmp != answer:
                        console.print(Panel(
                            rtl_wrap(translated_cmp),
                            title=f"[bold magenta]AI Comparison ({target_lang})[/]",
                            border_style="magenta",
                        ))


def handle_result_selection(results: list, selected_platforms: list):
    choices = [f"{i}. {r.get('title', '')}" for i, r in enumerate(results, 1)]
    choices.append("Back")
    choice = questionary.select(
        "Select a project:",
        choices=choices,
        style=QUESTIONARY_STYLE,
    ).ask()
    if not choice or choice == "Back":
        return
    idx = int(choice.split(".")[0]) - 1
    result = results[idx]

    console.print()
    console.print(Panel(
        f"[bold white]{result.get('title', '')}[/]\n"
        f"[dim]{result.get('href', '')}[/]\n\n"
        f"{result.get('body', '')}",
        title=f"[cyan]{result.get('platform', '')}[/]",
        border_style="bright_black",
    ))

    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Summary",
                "Usage",
                "Translate description",
                "License info",
                "Clone command",
                "Find similar projects",
                "Open in browser",
                "Back",
            ],
            style=QUESTIONARY_STYLE,
        ).ask()

        if not action or action == "Back":
            break
        elif action == "Summary":
            action_summary(result)
        elif action == "Usage":
            action_usage(result)
            break
        elif action == "Translate description":
            action_translate_description(result)
        elif action == "License info":
            action_license_info(result)
        elif action == "Clone command":
            action_clone_command(result)
        elif action == "Find similar projects":
            action_similar_search(result, selected_platforms)
            break
        elif action == "Open in browser":
            action_open_browser(result.get("href", ""))


def analyze_by_url():
    url = questionary.text("Enter project URL:", style=QUESTIONARY_STYLE).ask()
    if not url:
        return
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")

    result = {
        "title": "/".join(path_parts[:2]) if len(path_parts) >= 2 else parsed.netloc,
        "href": url,
        "body": "",
        "stars": 0,
        "forks": 0,
        "language": "N/A",
        "license": "Unknown",
        "updated": "",
        "platform": parsed.netloc,
        "_match_pct": "\u2014",
    }

    if "github.com" in parsed.netloc and len(path_parts) >= 2:
        repo = "/".join(path_parts[:2])
        info = fetch_repo_info(repo)
        if info:
            result.update({
                "title": info.get("full_name", result["title"]),
                "body": info.get("description", "") or "",
                "stars": info.get("stargazers_count", 0),
                "forks": info.get("forks_count", 0),
                "language": info.get("language") or "N/A",
                "license": (info.get("license") or {}).get("spdx_id", "Unknown"),
                "updated": info.get("pushed_at", "")[:10],
            })

    console.print()
    console.print(Panel(
        f"[bold white]{result['title']}[/]\n"
        f"[dim]{result['href']}[/]\n\n"
        f"{result['body']}\n\n"
        f"Stars: [yellow]{result['stars']:,}[/]  |  "
        f"Forks: [blue]{result['forks']:,}[/]  |  "
        f"Language: [cyan]{result['language']}[/]  |  "
        f"License: [magenta]{result['license']}[/]",
        title="[cyan]Project Info[/]",
        border_style="bright_black",
    ))

    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Summary",
                "Usage",
                "Translate description",
                "License info",
                "Clone command",
                "Open in browser",
                "Back",
            ],
            style=QUESTIONARY_STYLE,
        ).ask()
        if not action or action == "Back":
            break
        elif action == "Summary":
            action_summary(result)
        elif action == "Usage":
            action_usage(result)
            break
        elif action == "Translate description":
            action_translate_description(result)
        elif action == "License info":
            action_license_info(result)
        elif action == "Clone command":
            action_clone_command(result)
        elif action == "Open in browser":
            action_open_browser(result["href"])


def search_flow():
    platform_choices = list(PLATFORMS.keys())
    selected = questionary.checkbox(
        "Select platforms to search:",
        choices=[questionary.Choice(p, checked=True) for p in platform_choices],
        style=QUESTIONARY_STYLE,
    ).ask()
    if not selected:
        console.print("[yellow]No platforms selected.[/]")
        return

    user_input = questionary.text(
        "Describe what you're looking for:",
        style=QUESTIONARY_STYLE,
    ).ask()
    if not user_input:
        return

    console.print()
    q_info = expand_query(user_input)
    console.print(
        f"[dim]Query:[/] [bold]{q_info['en_query']}[/]  "
        f"[dim]Language:[/] {q_info['language']}  "
        f"[dim]Type:[/] {q_info['type']}"
    )
    console.print()

    with Progress(SpinnerColumn(), TextColumn("[cyan]Searching platforms..."), transient=True) as p:
        p.add_task("", total=None)
        results = search_all(q_info, selected)

    if not results:
        console.print("[red]No results found. Try different keywords.[/]")
        return

    results = prefilter_results(results, q_info.get("keywords", []))

    with Progress(SpinnerColumn(), TextColumn("[cyan]AI ranking results..."), transient=True) as p:
        p.add_task("", total=None)
        results = ai_rank_results(results, user_input)

    console.print(f"[green]Found {len(results)} results[/]\n")
    display_results_table(results)
    console.print()
    handle_result_selection(results, selected)


def main():
    print_logo()
    while True:
        choice = questionary.select(
            "Main Menu:",
            choices=[
                "Search for projects",
                "Analyze project by URL",
                "Compare projects",
                "Exit",
            ],
            style=QUESTIONARY_STYLE,
        ).ask()

        if not choice or choice == "Exit":
            console.print("[dim]Goodbye.[/]")
            break
        elif choice == "Search for projects":
            search_flow()
        elif choice == "Analyze project by URL":
            analyze_by_url()
        elif choice == "Compare projects":
            compare_projects()

        console.print()


if __name__ == "__main__":
    main()
