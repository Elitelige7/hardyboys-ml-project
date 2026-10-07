import joblib

model = joblib.load("models/logistic_regression.joblib")

def predict_sentiment(review):
    return model.predict([review])[0]


if __name__ == "__main__":
    review = input("Enter a movie review: ")
    print("Predicted sentiment:", predict_sentiment(review))