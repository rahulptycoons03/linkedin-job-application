"""Robot Framework variable file for LinkedIn Easy Apply – Singapore Data Engineer (rahul-sg)."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load credentials from rahul-sg-data-engineer profile
_profile = ROOT / "config" / "profiles" / "rahul-sg-data-engineer"
sys.path.insert(0, str(_profile))
import importlib.util
_spec = importlib.util.spec_from_file_location("secrets", _profile / "secrets.py")
_secrets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_secrets)

USERNAME = _secrets.username
PASSWORD = _secrets.password
LINKEDIN_HOME = "https://www.linkedin.com"
LINKEDIN_LOGIN = "https://www.linkedin.com/login"
KEYWORDS = ["data engineer"]
LOCATION = "Singapore"
MAX_APPLICATIONS = 10
# Override via robot -v BROWSER:headlesschrome for scheduled/headless runs
BROWSER = "chrome"


def _search_url(keywords: str, location: str) -> str:
    kw = quote_plus(keywords)
    loc = quote_plus(location)
    return f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&f_AL=true&sortBy=R"


SEARCH_URLS = [_search_url(k, LOCATION) for k in KEYWORDS]
