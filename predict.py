import joblib
import numpy as np
from scipy.sparse import csr_matrix

artifact = joblib.load("baseline.joblib")
model = artifact["model"]
feature_index = artifact["feature_index"]

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
