from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.core.config import settings

class TextChunker:
    def __init__(self):
        # Chunker: Cắt theo kích thước và ngữ nghĩa câu
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", "?", "!", " ", ""]
        )

    def chunk_data(self, text: str):
        """Cắt văn bản thành các chunks nhỏ"""
        return self.text_splitter.split_text(text)

# Singleton instance
chunker = TextChunker()
