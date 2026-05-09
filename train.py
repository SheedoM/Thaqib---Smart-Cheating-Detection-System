import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

from utils import load_data
from config import MODEL_PATH

def extract_features(signal):
    return [
        np.mean(signal),
        np.std(signal),
        np.max(signal),
        np.min(signal)
    ]

def train():
    X_raw, y = load_data()

    X = [extract_features(x) for x in X_raw]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(n_estimators=100)
    model.fit(X_train, y_train)

    acc = model.score(X_test, y_test)
    print(f"Accuracy: {acc:.2f}")

    joblib.dump(model, MODEL_PATH)
    print("Model saved!")

if __name__ == "__main__":
    train()
