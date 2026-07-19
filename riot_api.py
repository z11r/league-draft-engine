"""Minimal Riot API client with rate limiting baked in.

Riot has two kinds of hosts:
  platform hosts (na1, euw1, kr, ...)          -> league-v4 (rankings)
  regional hosts (americas, europe, asia, sea) -> match-v5  (match data)

A development key allows 20 requests/s and 100 requests/2min. The 2-minute
window is the binding constraint: 100 req / 120 s = one request per 1.2 s,
so we simply pace every request to that interval instead of tracking both
windows separately.
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

MIN_INTERVAL = 1.2  # seconds between requests (dev key: 100 req / 2 min)

REGION_FOR_PLATFORM = {
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
    "kr": "asia", "jp1": "asia",
    "oc1": "sea", "sg2": "sea", "tw2": "sea", "vn2": "sea",
}


class RiotClient:
    def __init__(self, platform: str):
        api_key = os.getenv("RIOT_API_KEY")
        if not api_key:
            raise SystemExit("RIOT_API_KEY not set — copy .env.example to .env and add your key")
        self.platform = platform
        self.region = REGION_FOR_PLATFORM[platform]
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers["X-Riot-Token"] = api_key

    def _get(self, host: str, path: str, params: dict | None = None):
        while True:
            wait = MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

            try:
                resp = self.session.get(
                    f"https://{host}.api.riotgames.com{path}", params=params, timeout=30
                )
            except requests.RequestException as exc:
                print(f"  network error ({exc.__class__.__name__}), retrying in 10s")
                time.sleep(10)
                continue

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "10"))
                print(f"  rate limited, sleeping {retry_after}s")
                time.sleep(retry_after)
                continue
            if resp.status_code >= 500:
                time.sleep(10)
                continue
            resp.raise_for_status()
            return resp.json()

    def league_entries(self, tier: str) -> list[dict]:
        """All players in an apex league. tier: challenger|grandmaster|master."""
        data = self._get(
            self.platform, f"/lol/league/v4/{tier}leagues/by-queue/RANKED_SOLO_5x5"
        )
        return data["entries"]

    def match_ids(self, puuid: str, count: int = 100) -> list[str]:
        """Most recent ranked solo-queue match ids for a player (queue 420)."""
        return self._get(
            self.region,
            f"/lol/match/v5/matches/by-puuid/{puuid}/ids",
            params={"queue": 420, "start": 0, "count": count},
        )

    def match(self, match_id: str) -> dict:
        return self._get(self.region, f"/lol/match/v5/matches/{match_id}")
