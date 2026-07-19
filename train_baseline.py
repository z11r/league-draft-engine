from db import connect
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss

conn = connect()
rows = conn.execute("""
    SELECT blue_top, blue_jungle, blue_mid, blue_bot, blue_support,
            red_top, red_jungle, red_mid, red_bot, red_support,
            blue_win, game_creation 
    FROM matches
    WHERE patch IN ('16.10', '16.11', '16.12', '16.13', '16.14')
    ORDER BY game_creation
    """).fetchall()


SLOTS = ["blue_top", "blue_jungle", "blue_mid", "blue_bot", "blue_support",
         "red_top", "red_jungle", "red_mid", "red_bot", "red_support"]

feature_index = {}
for row in rows:
    for slot, champ in zip(SLOTS, row[:10]):
        key = (slot, champ)
        if key not in feature_index:
            feature_index[key] = len(feature_index)

row_idx, col_idx = [], []
for i, row in enumerate(rows):
    for slot, champ in zip(SLOTS, row[:10]):
        row_idx.append(i)
        col_idx.append(feature_index[(slot, champ)]) 

X = csr_matrix((np.ones(len(row_idx)), (row_idx, col_idx)), shape=(len(rows), len(feature_index)))
y = np.array([row[10] for row in rows])

split = int(len(rows) * 0.9)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)

acc = accuracy_score(y_test, model.predict(X_test))
ll = log_loss(y_test, model.predict_proba(X_test))
majority = max(y_test.mean(), 1 - y_test.mean())

print(f"always-red baseline: {majority:.4f}")
print(f"model accuracy:      {acc:.4f}")
print(f"model log loss:      {ll:.4f}")
