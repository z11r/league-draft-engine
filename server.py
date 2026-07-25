"""
Run:
    uvicorn server:app --reload --port 8000
Needs baseline.joblib next to predict.py. Serves the UI from static/ if present,
so relative API paths work the same in dev and prod.
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from predict import predict_win, recommend, list_champions, ROLES


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
    slot: str


app = FastAPI(title="Draft Engine")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/champions")
def champions():
    return {"champions": list_champions()}


@app.post("/predict")
def predict(req: PredictReq):
    blue, red = req.blue.model_dump(), req.red.model_dump()
    filled = [c for c in list(blue.values()) + list(red.values()) if c]
    if len(filled) != 10:
        raise HTTPException(status_code=422, detail="all 10 slots must be filled")
    return {"blue_win_probability": predict_win(blue, red)}


@app.post("/recommend")
def recommend_slot(req: RecommendReq):
    side, _, role = req.slot.partition("_")
    if side not in ("blue", "red") or role not in ROLES:
        raise HTTPException(status_code=422, detail="bad slot")
    ranked = recommend(req.blue.model_dump(), req.red.model_dump(), req.slot)
    return {
        "recommendations": [
            {"champion": champ, "win_probability": win} for champ, win in ranked
        ]
    }


if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
