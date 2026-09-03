import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer


class Embedder:
    """
    Fixed-size text representation for MUSA.

    This currently uses HashingVectorizer rather than
    a transformer-based semantic embedding model.
    """

    def __init__(self, n_features=384):
        self.n_features = n_features

        self.vectorizer = HashingVectorizer(
            n_features=self.n_features,
            alternate_sign=False,
            norm="l2",
            lowercase=True,
            stop_words="english",
        )

    def encode(self, text):
        """
        Convert text into a fixed-size vector.
        """

        if not text or not str(text).strip():
            return [0.0] * self.n_features

        try:
            vector = (
                self.vectorizer
                .transform([str(text)])
                .toarray()[0]
            )

            return vector.astype(
                np.float32
            ).tolist()

        except Exception as e:

            print(
                "[EMBEDDING ERROR] {}".format(e),
                flush=True,
            )

            return [0.0] * self.n_features

    @staticmethod
    def cosine_similarity(v1, v2):
        """
        Calculate cosine similarity between two vectors.
        """

        a = np.asarray(
            v1,
            dtype=np.float32,
        )

        b = np.asarray(
            v2,
            dtype=np.float32,
        )

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(
            np.dot(a, b)
            / (norm_a * norm_b)
        )
