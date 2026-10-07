import pandas as pd
from pathlib import Path
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score
from sklearn.linear_model import LogisticRegression


df = pd.read_csv("data/IMDB Dataset.csv")
df = df[["review", "sentiment"]].dropna().drop_duplicates(subset=["review"])

X_train, X_test, y_train, y_test = train_test_split(
    df["review"],
    df["sentiment"],
    test_size=0.2,
    random_state=42,
    stratify=df["sentiment"],
)

model = Pipeline([
    ("tfidf", TfidfVectorizer(max_features=50000, ngram_range=(1, 2))),
    ("classifier", MultinomialNB()),
])

model.fit(X_train, y_train)
predictions = model.predict(X_test)

print("Naive Bayes results")
print("Accuracy:", round(accuracy_score(y_test, predictions), 4))
print("Macro F1:", round(f1_score(y_test, predictions, average="macro"), 4))


logistic_model = Pipeline([
    ("tfidf", TfidfVectorizer(max_features=50000, ngram_range=(1, 2))),
    ("classifier", LogisticRegression(max_iter=1000)),
])

logistic_model.fit(X_train, y_train)
logistic_predictions = logistic_model.predict(X_test)

print("\nLogistic Regression results")
print("Accuracy:", round(accuracy_score(y_test, logistic_predictions), 4))
print("Macro F1:", round(f1_score(y_test, logistic_predictions, average="macro"), 4))

Path("models").mkdir(exist_ok=True)
joblib.dump(model, "models/naive_bayes.joblib")
joblib.dump(logistic_model, "models/logistic_regression.joblib")
print("Models saved in the models folder.")