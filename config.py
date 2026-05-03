"""Project configuration: paths, API endpoints, rate limits, scoring weights."""
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
RAW = ROOT / "raw"
VIEWER = ROOT / "viewer"

ANIME_JSON = DATA / "anime.json"
ENTRIES_RAW = DATA / "entries.raw.json"
UNRESOLVED = DATA / "unresolved.json"
GRAPH_JSON = DATA / "graph.json"
GENRE_ZH_MAP = DATA / "genre_zh_map.json"
UNMAPPED_TAGS = DATA / "unmapped_tags.json"
MANUAL_OVERRIDES = DATA / "manual_overrides.json"
CHECKPOINT = DATA / "checkpoint.json"
COVERS_DIR = DATA / "covers"
CACHE_DIR = DATA / "cache"
RAW_LIST = RAW / "anime_list.txt"
USER_LISTS = DATA / "user_lists.json"

ANILIST_GRAPHQL = "https://graphql.anilist.co"
JIKAN_BASE = "https://api.jikan.moe/v4"
BANGUMI_BASE = "https://api.bgm.tv"

RATE_LIMITS = {
    "anilist": 0.7,
    "jikan": 0.4,
    "bangumi": 1.0,
}

REQUEST_TIMEOUT = 15
RETRY_MAX = 3
RETRY_BACKOFF = 2.0

RATING_WEIGHTS = {
    "anilist": 0.5,
    "mal": 0.3,
    "bangumi": 0.2,
}

MATCH_AUTO_ACCEPT = 0.85
MATCH_REVIEW_THRESHOLD = 0.6

ENRICH_TTL_DAYS = 90

COVER_MAX_PX = 600

GRAPH_DEFAULTS = {
    "weight_threshold": 0.4,
    "hub_max_degree": 30,
    "edge_weights": {
        "franchise": 1.0,
        "same_studio": 0.3,
        "shared_genre_per_overlap": 0.2,
        "shared_tag_per_overlap": 0.15,
        "same_year": 0.1,
    },
    "tag_strong_rank_min": 85,
    "tag_keep_rank_min": 60,
}

USER_AGENT = "kiuno-anime-viewer/0.1 (personal use)"

SERVE_PORT = 8000
