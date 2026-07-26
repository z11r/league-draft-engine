## League Draft Engine

Predicts the win probability of a League of Legends draft, and suggests the best next champion pick.
Trained off of around 100k high elo ranked games.

There's a small web UI for building drafts and getting live predictions:
<img width="2556" height="1305" alt="Screenshot 2026-07-25 172954" src="https://github.com/user-attachments/assets/0fb3daa3-e79e-4069-84fe-b763b57bb2ca" />

<img width="2554" height="1304" alt="Screenshot 2026-07-25 173102" src="https://github.com/user-attachments/assets/1803c550-71bb-4193-9767-fd69f104cdcd" />

## The Data

The match data comes from the Riot API, a collector gets the match data from NA and EUW.

There are around 106k games at the moment from patches 16.10 to 16.14.

## The Model

The baseline is a simple logistic regression. Each game becomes a sparce one hot vector with every slot and champion pair. The model learns a weight for each feature and adds them up.

- Majority class baseline: 52.2% accuracy
- Logistic regression: 54.4% accuracy

The draft only matters a little bit which lines up with reality, as high elo games are often decided by player skill rather than champion composition.

I picked the regularization strength (`C`) by log loss, not accuracy, because the recommender ranks champions by probability. I care that the probabilities are calibrated, not just which side of 50% they land on. `C=0.01` won.

The first version of the reccomend function just too the argmax over evey champion, so champions with a tiny sample size would have a much higher weight and be at the top of every list. I fixed this by using:

- Regularization: pulls the extreme weights back toward zero (the C sweep)
- A minimum games threshold: a minimum games threshold in predict.py that drops anything with a small sample size.

## A current limitation:

Because the linear model just adds a constant per enemy pick, the enemy comp changes the probability but not the ranking of the reccomendations. The next step for the project is to add this functionality.

## Roadmap

Future features:

- Interaction terms so the model can read counters and synergies
- Lane-level win labels. Right now a win is a whole team win. Knowing who won their
  lane would be a much stronger signal for counters than the final result.
- More data across a wider skill range.
- Matchup priors to seed the counter logic from known lane matchups instead of
  learning everything from scratch.

# Running it

```bash
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

Then open http://127.0.0.1:8000/

To generate the model:

```bash
python train_baseline.py
```

The sqlite match data file also needs to be present, where you will need your own riot API key, so it will need to be copied to .env and the collector needs to be ran.
