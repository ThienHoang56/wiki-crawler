from sentence_transformers import SentenceTransformer
from src.core.config import settings
from typing import List

class Embedder:
    _model: SentenceTransformer = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy init: chỉ load model khi lần đầu được gọi, không phải lúc import."""
        if self._model is None:
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model

    def get_embedding(self, text: str) -> List[float]:
        """Tạo vector 384 dims cho một đoạn văn bản."""
        return self.model.encode(text).tolist()

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Tạo embeddings hàng loạt để tối ưu hiệu suất."""
        return self.model.encode(texts).tolist()

embedder = Embedder()
