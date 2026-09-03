from sentence_transformers import SentenceTransformer
import numpy as np


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Load the pre-trained model.
        self.model = SentenceTransformer(model_name)

    def encode(self, text: str) -> list[float]:
        # Convert text to a vector (embedding).
        embedding = self.model.encode(text)
        return embedding.tolist()

    @staticmethod
    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        # Compute the cosine similarity between two vectors.
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        return float(dot_product / (norm_v1 * norm_v2))
