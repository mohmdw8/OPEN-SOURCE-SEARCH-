from unittest.mock import patch, MagicMock
import json
import pytest

from search_engines.platform_base import smart_deduplicate, prefilter_results
from search_engines.github_search import search_github
from main import search_all, _filter_low_quality
from ai_backend.ranking import ai_rank_results


@pytest.fixture
def mock_github_response():
    return {
        "items": [
            {
                "full_name": "psf/requests",
                "html_url": "https://github.com/psf/requests",
                "description": "A simple HTTP library for Python",
                "stargazers_count": 53000,
                "forks_count": 9500,
                "watchers_count": 53000,
                "language": "Python",
                "license": {"spdx_id": "Apache-2.0"},
                "pushed_at": "2025-12-01T00:00:00Z",
                "open_issues_count": 120,
                "archived": False,
            },
            {
                "full_name": "archived/old-project",
                "html_url": "https://github.com/archived/old-project",
                "description": "An old archived project",
                "stargazers_count": 100,
                "forks_count": 10,
                "watchers_count": 100,
                "language": "Python",
                "license": {"spdx_id": "MIT"},
                "pushed_at": "2020-01-01T00:00:00Z",
                "open_issues_count": 0,
                "archived": True,
            },
            {
                "full_name": "no-desc/repo",
                "html_url": "https://github.com/no-desc/repo",
                "description": None,
                "stargazers_count": 50,
                "forks_count": 5,
                "watchers_count": 50,
                "language": "Python",
                "license": {"spdx_id": "MIT"},
                "pushed_at": "2024-06-01T00:00:00Z",
                "open_issues_count": 2,
                "archived": False,
            },
        ]
    }


@pytest.fixture
def mock_ddg_results():
    return [
        {
            "title": "GitLab Project",
            "href": "https://gitlab.com/owner/project",
            "body": "A project on GitLab",
        }
    ]


class MockDDGS:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def text(self, query, max_results=4):
        return [
            {
                "title": "Test Project on GitLab",
                "href": "https://gitlab.com/test/project",
                "body": "A test project hosted on GitLab",
            }
        ]

    def chat(self, prompt, model="gpt-4o-mini"):
        return json.dumps({
            "sub_queries": ["http library python"],
            "query1": "http client python",
            "query2": "requests library",
            "query3": "python networking",
            "keywords": ["http", "python", "requests"],
            "language": "Python",
            "type": "library",
        })


@pytest.fixture(autouse=True)
def mock_external_calls(monkeypatch):
    monkeypatch.setattr(
        "duckduckgo_search.DDGS",
        MockDDGS,
    )


def test_integration_full_search_workflow(mock_github_response):
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_github_response
        mock_get.return_value = mock_resp

        results = search_github("http library", max_results=3)
        assert len(results) == 3

        for r in results:
            assert r["platform"] == "GitHub"
            assert r["_from_api"] is True

        assert results[0]["title"] == "psf/requests"
        assert results[1]["title"] == "archived/old-project"
        assert results[2]["title"] == "no-desc/repo"


def test_integration_filter_removes_archived(mock_github_response):
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_github_response
        mock_get.return_value = mock_resp

        results = search_github("http library", max_results=3)
        filtered = _filter_low_quality(results)

        titles = [r["title"] for r in filtered]
        assert "psf/requests" in titles
        assert "archived/old-project" not in titles
        assert "no-desc/repo" not in titles


def test_integration_deduplication():
    results = [
        {"title": "owner/repo", "href": "https://github.com/owner/repo", "stars": 5, "body": "desc"},
        {"title": "owner/repo", "href": "https://github.com/owner/repo.git", "stars": 100, "body": "desc"},
        {"title": "owner/other", "href": "https://github.com/owner/other", "stars": 50, "body": "desc"},
    ]
    deduped = smart_deduplicate(results)
    assert len(deduped) == 2
    stars = [r["stars"] for r in deduped]
    assert 100 in stars
    assert 50 in stars


def test_integration_prefilter_ranking_pipeline():
    results = [
        {"title": "req/python", "href": "https://github.com/req/python", "body": "HTTP requests for Python", "stars": 100, "usage": 5000, "usage_label": "dl/month", "platform": "GitHub", "license": "MIT", "language": "Python"},
        {"title": "flask/web", "href": "https://github.com/flask/web", "body": "Web framework", "stars": 200, "usage": 10000, "usage_label": "dl/month", "platform": "GitHub", "license": "BSD", "language": "Python"},
        {"title": "node/http", "href": "https://github.com/node/http", "body": "HTTP client for Node.js", "stars": 50, "usage": 2000, "usage_label": "dl/week", "platform": "npm", "license": "MIT", "language": "JavaScript"},
    ]

    filtered = prefilter_results(results, ["http", "python"])
    assert len(filtered) >= 1

    ranked = ai_rank_results(filtered, "http client library")
    assert len(ranked) > 0
    assert "_score" in ranked[0]
    assert "_match_pct" in ranked[0]


def test_integration_search_all_returns_filtered(mock_github_response):
    query_info = {
        "sub_queries": ["http library python"],
        "en_query": "http client python",
        "alt_queries": ["requests library"],
        "keywords": ["http", "python", "requests"],
        "language": "Python",
        "type": "library",
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_github_response
        mock_get.return_value = mock_resp

        results = search_all(query_info, ["GitHub", "GitLab"], max_per=3)
        assert isinstance(results, list)
        assert len(results) > 0

        titles = [r["title"] for r in results]
        assert "psf/requests" in titles
        assert "archived/old-project" not in titles
        assert "no-desc/repo" not in titles

        for r in results:
            body = (r.get("body") or "").strip()
            if r.get("archived", False):
                assert False, "archived repo should be filtered"
            if not body and r.get("platform") == "GitHub":
                assert False, "GitHub repo without description should be filtered"


def test_integration_rank_sorting():
    results = [
        {"title": "proj/a", "href": "https://github.com/proj/a", "body": "http client", "stars": 10, "usage": 100, "usage_label": "dl", "platform": "GitHub", "license": "MIT", "language": "Python"},
        {"title": "proj/b", "href": "https://github.com/proj/b", "body": "http client advanced", "stars": 500, "usage": 5000, "usage_label": "dl", "platform": "GitHub", "license": "MIT", "language": "Python"},
        {"title": "proj/c", "href": "https://github.com/proj/c", "body": "unrelated tool", "stars": 1000, "usage": 10000, "usage_label": "dl", "platform": "GitHub", "license": "MIT", "language": "Python"},
    ]

    ranked = ai_rank_results(results, "http client library")
    assert ranked[0]["_score"] >= 0
    assert ranked[0]["_score"] <= 100


def test_integration_empty_results():
    assert search_all({"sub_queries": [], "en_query": "", "alt_queries": [], "keywords": [], "language": "Any", "type": "any"}, []) == []
    assert _filter_low_quality([]) == []
    assert smart_deduplicate([]) == []
    assert ai_rank_results([], "test") == []
