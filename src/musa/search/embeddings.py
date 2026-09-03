import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from pathlib import Path

class Embedder:
    """
    Stateless embedding system using HashingVectorizer.
    This provides fixed-size vectors (384-dim) without requiring a fit/train step,
    making it perfect for real-time crawling and cloud deployment.
    """
    def __init__(self, n_features: int = 384) -> None:
        self.n_features = n_features
        # HashingVectorizer is stateless - it doesn't need to be 'fit' to a corpus.
        self.vectorizer = HashingVectorizer(n_features=self.n_features, alternate_sign=False)

    def encode(self, text: str) -> list[float]:
        """Turns text into a fixed-size vector."""
        try:
            # Transform returns a sparse matrix; we convert to a dense numpy array
            vector = self.vectorizer.transform([text]).toarray()[0]
            return vector.tolist()
        except Exception as e:
            print(f"Embedding error: {e}")
            return [0.0] * self.n_features

    @staticmethod
    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        a = np.array(v1)
        b = np.array(v2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
