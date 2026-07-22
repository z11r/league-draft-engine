import joblib
import numpy as np
from scipy.sparse import csr_matrix

MIN_GAMES = 100
TOP = 10

artifact = joblib.load("baseline.joblib")
model = artifact["model"]
feature_index = artifact["feature_index"]
feature_counts = artifact["feature_counts"]

ROLES = ["top", "jungle", "mid", "bot", "support"]


def predict_win(blue_comp, red_comp):
    cols = []
    for side, comp in [("blue", blue_comp), ("red", red_comp)]:
        for role in ROLES:
            key = (f"{side}_{role}", comp[role])
            if key in feature_index:
                cols.append(feature_index[key])
    x = csr_matrix((np.ones(len(cols)), ([0] * len(cols), cols)), shape=(1, len(feature_index)))
    return float(model.predict_proba(x)[0, 1])


def recommend(blue_comp, red_comp, slot):
    side, role = slot.split("_")
    if side == "blue":
        comp = blue_comp
    else:
        comp = red_comp

    taken = set(blue_comp.values()) | set(red_comp.values())
    original = comp[role]
    scores = []
    for key_slot, champ in feature_index:
        if key_slot != slot or champ in taken or feature_counts[(key_slot, champ)] < MIN_GAMES:
            continue
        comp[role] = champ
        win = predict_win(blue_comp, red_comp)
        if side == "red":
            win = 1 - win
        scores.append((champ, win))
    comp[role] = original

    scores.sort(key=lambda pair: pair[1], reverse=True)
    return scores[:TOP]

