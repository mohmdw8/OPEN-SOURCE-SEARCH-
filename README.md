# OpenSourceSearch

<img width="311" height="213" alt="Image" src="https://github.com/user-attachments/assets/3f2f37be-33ad-4c20-95ed-9a4848a83e45" />

Search for open-source projects in any language. Describe what you need in plain English, Arabic, French, or any language — the tool handles translation, searches 9 platforms simultaneously, and ranks results with AI.

## What is OpenSourceSearch?

A CLI tool that searches for open-source projects across **9 platforms** simultaneously. Describe what you need in simple terms in your own language — Arabic, French, Japanese, or any other — and the tool automatically handles translation, searching, and ranking using AI.

```
Description in any language → Translation to English → Parallel search across 9 platforms → Smart ranking → Accurate results
```

## Project Structure

```
OpenSourceSearch/
├── main.py                  # CLI entry point (actions, menus, orchestration)
├── .env.example             # Environment variables template (copy to .env)
├── .gitignore
├── core/
│   ├── config.py            # Constants, API keys, platforms, license map
│   └── cache.py             # Atomic file writes, similarity-based cache lookup
├── search_engines/
│   ├── platform_base.py     # DDG search, dedup, keyword prefilter
│   ├── github_search.py     # GitHub REST API (reads GITHUB_TOKEN from .env)
│   ├── pypi_search.py       # PyPI JSON API (with XML-RPC fallback)
│   ├── npm_search.py        # npm registry API
│   ├── huggingface_search.py
│   └── docker_search.py
├── ai_backend/
│   ├── llm_handler.py       # DuckDuckGo Chat primary, Pollinations/g4f fallbacks
│   └── ranking.py           # AI scoring: 50% match + 30% stars + 20% usage
└── utils/
    ├── translation.py       # Multi-script language detection (Arabic, CJK, Cyrillic, etc.)
    └── logger.py            # Centralized file logging
```

## Supported Platforms

| Platform         | Connection Type | Available Data                               |
| :--------------- | :-------------- | :------------------------------------------- |
| **GitHub**       | Direct API      | Stars, forks, language, license, last update |
| **Hugging Face** | Direct API      | Likes, downloads, model categories           |
| **PyPI**         | Direct API      | Monthly downloads                            |
| **npm**          | Direct API      | Weekly downloads                             |
| **Docker Hub**   | Direct API      | Number of pulls                              |
| **GitLab**       | DuckDuckGo      | Targeted search results                      |
| **Bitbucket**    | DuckDuckGo      | Targeted search results                      |
| **Codeberg**     | DuckDuckGo      | Targeted search results                      |
| **SourceForge**  | DuckDuckGo      | Targeted search results                      |

## Features

### 🌍 Support for Any Language in the World

Write your query in any non-English language. Translation chain:

```
Google Translate → deep_translator → MyMemory → Lingva → Built-in dictionary fallback
```

Language detection now supports **Arabic, Japanese, Korean, Russian, Hindi, Chinese, and more** — not just Arabic vs English.

### 🤖 AI Query Expansion

The AI analyzes your description and generates:
- **sub_queries** — multiple concepts broken into separate searches
- **query1 / query2 / query3** — precise technical keywords
- **keywords** — vocabulary for preliminary filtering
- **language / type** — suggested programming language and project type

### ⚡ High-Speed Parallel Search

Searches all platforms concurrently via `ThreadPoolExecutor` (max 25s timeout). Automatic DuckDuckGo fallback if any API fails.

### 🧠 Smart AI Ranking

Each result scored as: **50% description match + 30% star count + 20% usage/downloads**. AI evaluates semantic relevance, not just keyword matching.

### 💾 Smart Cache System

- Saves previous queries in `query_cache.json`
- Reuses cached results at ≥80% similarity via difflib
- Auto-evicts oldest 10% of entries when exceeding 100,000 words
- Atomic writes via `tempfile.mkstemp` + `os.replace` — no data corruption on interrupt

### 🤖 Multi-Layer AI Engines

Priority order to guarantee a response:

```
DuckDuckGo Chat (GPT-4o-mini) → DuckDuckGo Chat (Claude 3 Haiku) → Pollinations AI → g4f
```

## Installation

### Prerequisite: Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Or via pip: `pip install uv`

### Setup

```bash
# 1. Clone
git clone https://github.com/asaadzx/OpenSourceSearch.git
cd OpenSourceSearch

# 2. Install dependencies & create venv
uv sync

# 3. (Optional) Configure GitHub token for higher API rate limits
cp .env.example .env
# Then edit .env with your GitHub token

# 4. Run
uv run python3 main.py
```

For development (includes pytest):
```bash
uv sync --extra dev
uv run pytest tests/ -q
```

> **Note:** `g4f` is optional (`uv sync --extra ai`) — the tool defaults to DuckDuckGo Chat which is faster and more stable.

### GitHub Token (Recommended)

To avoid GitHub API rate limits (60 req/hr unauthenticated vs 5000 req/hr authenticated), provide a token via **either** method:

**Option 1 — `.env` file (persistent, recommended):**
```bash
cp .env.example .env
# Then edit .env:
#   GITHUB_TOKEN="ghp_your_token_here"
```

**Option 2 — Environment variable (session only):**
```bash
export GITHUB_TOKEN="your_github_token"
```

Create a token at https://github.com/settings/tokens — no scopes are needed for public repository searches.

## How to Use

### 1. Searching for a Project

```
python3 main.py
```

Select **Search for projects**, choose platforms, describe what you need in any language:

```
# Arabic: أداة لفحص شبكات الواي فاي
# English: web scraper with javascript support
# French: outil de compression de fichiers
# Japanese: スクリーンショットを撮るツール
```

### 2. Available Actions for Each Project

| Action                    | Function                                                           |
| :------------------------ | :----------------------------------------------------------------- |
| **Summary**               | AI-generated summary from the README                               |
| **Usage**                 | Installation and usage steps with copy-ready commands              |
| **Translate description** | Translate the description into any language                        |
| **License info**          | Allowed / Forbidden / Conditions for the project's license         |
| **Clone command**         | Ready-to-copy `git clone` command                                  |
| **Find similar projects** | Auto-search for related projects                                   |
| **Open in browser**       | Open the project URL in your browser                               |

### 3. Analyze by URL

Paste a URL directly (e.g., `https://github.com/owner/repo`) to inspect a project without searching.

### 4. Compare Projects

Enter 2–4 project URLs or names. Get a feature comparison table and AI-powered analysis.

## How It Works

```
┌──────────────────────────────────────────┐
│              User Request                │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│          Language Detection              │
│     (Arabic / Japanese / Korean / etc.)  │
└────────────────┬─────────────────────────┘
                 │ (non-English)
                 ▼
┌──────────────────────────────────────────┐
│         Translate to English             │
│    Google → MyMemory → Lingva → fallback │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│          AI Query Expansion              │
│ sub_queries + q1/q2/q3 + keywords + lang │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│      Parallel Search (9 Platforms)       │
│     ThreadPoolExecutor (max 25s)         │
├──────────────────────┬───────────────────┤
│   Direct API          │   DDG Fallback   │
│ GitHub / HuggingFace  │ GitLab/Bitbucket │
│ PyPI / npm / Docker   │ Codeberg/SF      │
└──────────────────────┴───────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│          Smart Deduplication             │
│     (by URL + normalized project name)   │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│       AI Pre-filter + Ranking            │
│    50% match + 30% stars + 20% usage     │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│         Results Table + Actions          │
└──────────────────────────────────────────┘
```

## Supported Licenses

| License             | Allowed                                    | Conditions / Requirements                          |
| :------------------ | :----------------------------------------- | :------------------------------------------------- |
| **MIT**             | Commercial use, modification, distribution | Include license and copyright notice               |
| **Apache 2.0**      | Commercial use, patent rights              | State changes made to files                        |
| **GPL v3**          | Commercial use, modification               | Disclose source code                               |
| **AGPL v3**         | Commercial use, modification               | Disclose source code even when hosted over network |
| **BSD 2/3**         | Commercial use, distribution               | Include license and copyright notice               |
| **Unlicense / CC0** | Everything — Public Domain                 | None                                               |

## Requirements

- Python 3.8+
- Active internet connection
- Tested on Linux, Termux, macOS

## Notes

- The tool is designed to work even if a module fails — every component has an automated fallback
- No API key is required, but a **GitHub token** is recommended for higher rate limits
- Put your `GITHUB_TOKEN` in a `.env` file (copy from `.env.example`) — it's loaded automatically and won't be committed
- PyPI and Docker Hub results may be less precise than GitHub results
- g4f is available as a last-resort fallback but is **not required** — DDG Chat is preferred

## Roadmap

### Phase 1: Critical Bug Fixes ✅ (Complete)
- [x] **Fix Language Detection** — Now detects Arabic, Japanese, Korean, Russian, Hindi, Chinese
- [x] **GitHub Token Support** — `GITHUB_TOKEN` env var for 5000 req/hr
- [x] **Atomic Cache Writes** — `tempfile.mkstemp` + `os.replace` prevents corruption
- [x] **Replace g4f as Default** — DuckDuckGo Chat is now primary (faster, no IP bans)
- [x] **Migrate PyPI to JSON API** — JSON search primary, XML-RPC fallback
- [x] **Centralized Logging** — `utils/logger.py` replaces bare `except: pass`

### Phase 2: Improve Test Coverage 🔄 (In Progress)
- [x] Unit tests for search engines, translation, cache, AI ranking
- [ ] Integration tests for multi-platform search workflow
- [ ] CI pipeline (GitHub Actions)

### Phase 3: Performance & Features 📋 (Planned)
- [ ] Result pagination for large result sets
- [x] Filter by language, license, stars range, last update
- [ ] Config file support (`~/.config/opensourcesearch/config.json`)
- [ ] Shell completion scripts (bash/zsh)
- [x] Search result caching (individual results, not just queries)

### Phase 4: Long-term Vision 🔮 (Future)
- [ ] Go rewrite — single binary, no Python dependency
- [ ] Web UI alongside CLI
- [ ] REST API for third-party integration
- [ ] Package on PyPI (`pip install opensourcesearch`)

### Phase 5: Search Quality & Usability 📈 (Planned)
- [ ] **Fix Arabic (RTL) text rendering in terminal** — Panels and tables may still mis-align right-to-left scripts; needs proper Rich RTL support or custom alignment
- [ ] **Improve search result relevance** — fine-tune keyword extraction and boosting, filter low-quality repos (no description, archived)
- [ ] **Enhance usage fetching** — fall back to PyPI/npm/Docker Hub README when GitHub README unavailable, detect monorepo sub-packages
- [ ] Result sorting by stars, license, language before AI ranking
- [ ] Show more metadata per result (last commit date, open issues count)
- [ ] Multi-page results (scroll beyond top 15)
- [x] Better error messages when APIs fail, with retry hints
