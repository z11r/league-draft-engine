"""
Throwaway mock backend for UI development. NOT the real thing.
Implements exactly the agreed contract with hard-coded/fake data.

Run:
    pip install "fastapi[standard]"
    uvicorn mock_server:app --reload --port 8000
Then open http://127.0.0.1:8000/  (it also serves the static/ UI, so
relative API paths work in dev exactly like they will in production).
"""
import hashlib
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

CHAMPIONS = [
    "Aatrox", "Ahri", "Akali", "Alistar", "Amumu", "Ashe", "Camille", "Cassiopeia",
    "Darius", "Draven", "Ekko", "Ezreal", "Fiora", "Gnar", "Graves", "Gwen", "Hecarim",
    "Irelia", "Janna", "Jarvan", "Jax", "Jhin", "Jinx", "Kaisa", "Karma", "Kassadin",
    "Katarina", "Kayn", "Leblanc", "LeeSin", "Leona", "Lulu", "Lux", "Malphite",
    "Maokai", "MissFortune", "Nautilus", "Orianna", "Poppy", "Rakan", "Renekton",
    "Rell", "Sejuani", "Sett", "Sion", "Sylas", "Syndra", "Thresh", "TwistedFate",
    "Vi", "Viego", "Viktor", "Xayah", "Yasuo", "Yone", "Zed", "Zeri", "Zoe",
]

ROLES = ["top", "jungle", "mid", "bot", "support"]


class Team(BaseModel):
    top: Optional[str] = None
    jungle: Optional[str] = None
    mid: Optional[str] = None
    bot: Optional[str] = None
    support: Optional[str] = None


class PredictReq(BaseModel):
    blue: Team
    red: Team


class RecommendReq(BaseModel):
    blue: Team
    red: Team
    slot: str  # "<side>_<role>", e.g. "blue_mid"


app = FastAPI(title="Draft Engine (MOCK)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def _picked(*teams: Team) -> set[str]:
    out: set[str] = set()
    for t in teams:
        out.update(c for c in t.model_dump().values() if c)
    return out


def _fake_prob(seed: str) -> float:
    """Deterministic pseudo-probability in [0,1] so a given draft is stable."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    return round(int(h[:8], 16) / 0xFFFFFFFF, 2)


@app.get("/champions")
def champions():
    return {"champions": CHAMPIONS}


@app.post("/predict")
def predict(req: PredictReq):
    filled = [c for t in (req.blue, req.red) for c in t.model_dump().values() if c]
    if len(filled) != 10:
        raise HTTPException(status_code=422, detail="all 10 slots must be filled")
    return {"blue_win_probability": _fake_prob(",".join(filled))}


@app.post("/recommend")
def recommend(req: RecommendReq):
    side, _, role = req.slot.partition("_")
    if side not in ("blue", "red") or role not in ROLES:
        raise HTTPException(status_code=422, detail="bad slot")
    taken = _picked(req.blue, req.red)
    ranked = sorted(
        (c for c in CHAMPIONS if c not in taken),
        key=lambda c: _fake_prob(req.slot + c),
        reverse=True,
    )[:10]
    return {
        "recommendations": [
            {"champion": c, "win_probability": _fake_prob(req.slot + c)} for c in ranked
        ]
    }


# Serve the UI so dev matches prod (same-origin, relative paths). Optional in dev.
if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
