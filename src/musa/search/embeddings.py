```python
import numpy as np

from sklearn.feature_extraction.text import (
    HashingVectorizer,
)


class Embedder:
    """
    Fixed-size text representation used by the
    current MUSA prototype.

    NOTE:
    This is a hashing-based lexical representation,
    not a transformer semantic embedding.

    A transformer model such as
    sentence-transformers/all-MiniLM-L6-v2
    can replace this in a later semantic-search upgrade.
    """

    def __init__(
        self,
        n_features: int = 384,
    ) -> None:

        self.n_features = n_features

        self.vectorizer = HashingVectorizer(
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
            lowercase=True,
            stop_words="english",
        )

    def encode(
        self,
        text: str,
    ) -> list[float]:

        if not text or not text.strip():
            return [
                0.0
            ] * self.n_features

        vector = (
            self.vectorizer
            .transform(
                [text]
            )
            .toarray()[0]
        )

        return vector.astype(
            np.float32
        ).tolist()

    @staticmethod
    def cosine_similarity(
        v1: list[float],
        v2: list[float],
    ) -> float:

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

        if (
            norm_a == 0
            or norm_b == 0
        ):
            return 0.0

        return float(
            np.dot(a, b)
            / (
                norm_a
                * norm_b
            )
        )
```
