import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import os
from pathlib import Path

class Embedder:
    """
    Lightweight embedding system using TF-IDF.
    This replaces SentenceTransformers to ensure cloud compatibility.
    """
    def __init__(self, index_path: str = "data/tfidf.pkl"):
        self.index_path = Path(index_path)
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self._load_vectorizer()

    def _load_vectorizer(self):
        if self.index_path.exists():
            with open(self.index_path, "rb") as f:
                self.vectorizer = pickle.load(f)

    def save_vectorizer(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump(self.vectorizer, f)

    def encode(self, text: str) -> list[float]:
        # For TF-IDF, the vectorizer needs a corpus to fit.
        # Since this is used for single queries, we use the already fitted vectorizer.
        try:
            vector = self.vectorizer.transform([text]).toarray()[0]
            return vector.tolist()
        except Exception:
            # If not yet fitted, return a zero vector of the expected size
            return [0.0] * 384 # Keep dim compatible for now

    @staticmethod
    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        a = np.array(v1)
        b = np.array(v2)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
