import os
import json
import warnings
import logging
from questionary import Style

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

os.environ["G4F_QUIET"] = "1"
os.environ["G4F_NO_UPDATE_CHECK"] = "1"

_dotenv = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.isfile(_dotenv):
    for _line in open(_dotenv):
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _k, _v = _k.strip(), _v.strip().strip("\"'")
        if _k not in os.environ:
            os.environ[_k] = _v

TIMEOUTS = {
    "api_fast": 5,
    "api_main": 10,
    "ai": 25,
    "ddg": 8,
    "translate": 8,
}

PLATFORMS = {
    "GitHub": {"domain": "github.com", "api": "github"},
    "GitLab": {"domain": "gitlab.com", "api": "ddg"},
    "Bitbucket": {"domain": "bitbucket.org", "api": "ddg"},
    "Codeberg": {"domain": "codeberg.org", "api": "ddg"},
    "Hugging Face": {"domain": "huggingface.co", "api": "huggingface"},
    "SourceForge": {"domain": "sourceforge.net", "api": "ddg"},
    "PyPI": {"domain": "pypi.org", "api": "pypi"},
    "npm": {"domain": "npmjs.com", "api": "npm"},
    "Docker Hub": {"domain": "hub.docker.com", "api": "docker"},
}

_CONFIG_DIR = os.path.expanduser("~/.config/opensourcesearch")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.json")
DEFAULT_MAX_RESULTS = 6
DEFAULT_PLATFORMS = list(PLATFORMS.keys())

def _load_user_config() -> dict:
    try:
        if os.path.isfile(_CONFIG_PATH):
            with open(_CONFIG_PATH) as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                return {}
            return cfg
    except Exception:
        pass
    return {}

_USER_CFG = _load_user_config()

_override_platforms = _USER_CFG.get("platforms")
if isinstance(_override_platforms, list) and _override_platforms:
    DEFAULT_PLATFORMS = [p for p in _override_platforms if p in PLATFORMS] or DEFAULT_PLATFORMS

DEFAULT_MAX_RESULTS = _USER_CFG.get("max_results", DEFAULT_MAX_RESULTS)
if not isinstance(DEFAULT_MAX_RESULTS, int) or DEFAULT_MAX_RESULTS < 1:
    DEFAULT_MAX_RESULTS = 6

_user_timeouts = _USER_CFG.get("timeouts")
if isinstance(_user_timeouts, dict):
    for k in TIMEOUTS:
        if k in _user_timeouts and isinstance(_user_timeouts[k], (int, float)) and _user_timeouts[k] > 0:
            TIMEOUTS[k] = int(_user_timeouts[k])

_user_token = _USER_CFG.get("github_token", "")
if _user_token and not os.environ.get("GITHUB_TOKEN") and not os.environ.get("GH_TOKEN"):
    os.environ["GITHUB_TOKEN"] = _user_token

LICENSE_MAP = {
    "mit": {"name": "MIT", "allowed": "Commercial, Modify, Distribute, Private", "forbidden": "Liability, Warranty", "conditions": "Include license notice"},
    "apache-2.0": {"name": "Apache 2.0", "allowed": "Commercial, Modify, Distribute, Patent, Private", "forbidden": "Trademark, Liability", "conditions": "State changes, Include notice"},
    "gpl-3.0": {"name": "GPL v3", "allowed": "Commercial, Modify, Distribute, Patent, Private", "forbidden": "Sublicense, Liability", "conditions": "Disclose source, Same license"},
    "gpl-2.0": {"name": "GPL v2", "allowed": "Commercial, Modify, Distribute, Private", "forbidden": "Sublicense, Liability", "conditions": "Disclose source, Same license"},
    "lgpl-2.1": {"name": "LGPL 2.1", "allowed": "Commercial, Modify, Distribute, Private", "forbidden": "Liability, Warranty", "conditions": "Disclose library source changes"},
    "bsd-2-clause": {"name": "BSD 2-Clause", "allowed": "Commercial, Modify, Distribute, Private", "forbidden": "Liability, Warranty", "conditions": "Include license notice"},
    "bsd-3-clause": {"name": "BSD 3-Clause", "allowed": "Commercial, Modify, Distribute, Private", "forbidden": "Liability, Warranty, Endorsement", "conditions": "Include license notice"},
    "mpl-2.0": {"name": "MPL 2.0", "allowed": "Commercial, Modify, Distribute, Patent, Private", "forbidden": "Liability, Warranty", "conditions": "Disclose source, Include notice"},
    "agpl-3.0": {"name": "AGPL v3", "allowed": "Commercial, Modify, Distribute, Patent, Private", "forbidden": "Sublicense, Liability", "conditions": "Disclose source (incl. network use)"},
    "unlicense": {"name": "Unlicense", "allowed": "Everything — public domain", "forbidden": "Nothing", "conditions": "None"},
    "isc": {"name": "ISC", "allowed": "Commercial, Modify, Distribute, Private", "forbidden": "Liability, Warranty", "conditions": "Include license notice"},
    "cc0-1.0": {"name": "CC0 1.0", "allowed": "Everything — public domain", "forbidden": "Nothing", "conditions": "None"},
}
UNKNOWN_LICENSE = {"name": "Unknown", "allowed": "Check project page", "forbidden": "Possibly all rights reserved", "conditions": "Unknown"}

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

QUESTIONARY_STYLE = Style([
    ("qmark", "fg:#e5c07b bold"),
    ("question", "fg:#61afef bold"),
    ("answer", "fg:#98c379 bold"),
    ("pointer", "fg:#e06c75 bold"),
    ("highlighted", "fg:#c678dd bold"),
    ("selected", "fg:#98c379"),
    ("separator", "fg:#5c6370"),
    ("instruction", "fg:#5c6370 italic"),
    ("text", "fg:#abb2bf"),
    ("disabled", "fg:#5c6370 italic"),
])
