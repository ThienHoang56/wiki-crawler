import re

class TextCleaner:
    def clean_text(self, text: str) -> str:
        """
        Xử lý toàn bộ các loại markup đặc trưng của Wikipedia.
        Input có thể là plain text từ API (explaintext=True) vẫn giữ một số ký tự
        wiki đặc biệt cần lọc thêm.
        """
        # Xóa thẻ HTML còn sót (trường hợp parse HTML trực tiếp)
        text = re.sub(r'<[^>]+>', '', text)

        # Xóa wiki citation references: [1], [citation needed], [note 2]
        text = re.sub(r'\[\d+\]', '', text)
        text = re.sub(r'\[citation needed\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[note \d+\]', '', text, flags=re.IGNORECASE)

        # Xóa wiki template markup: {{...}}
        text = re.sub(r'\{\{[^}]*\}\}', '', text)

        # Xóa wiki internal links dạng [[File:...]] hoặc [[Image:...]]
        text = re.sub(r'\[\[(?:File|Image|Category)[^\]]*\]\]', '', text, flags=re.IGNORECASE)

        # Giải nén wiki internal link [[link|display]] -> display, [[link]] -> link
        text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)

        # Xóa external links [http://... text] -> text, [http://...] -> ''
        text = re.sub(r'\[https?://\S+\s+([^\]]+)\]', r'\1', text)
        text = re.sub(r'\[https?://\S+\]', '', text)

        # Xóa wiki heading markup: == Heading ==
        text = re.sub(r'={2,6}\s*(.*?)\s*={2,6}', r'\1', text)

        # Xóa bold/italic markup: '''text''' hoặc ''text''
        text = re.sub(r"'{2,3}", '', text)

        # Xóa bullet/indent ký tự đầu dòng: *, #, :, ;
        text = re.sub(r'^[\*#:;]+\s*', '', text, flags=re.MULTILINE)

        # Xóa table markup: {| ... |}
        text = re.sub(r'\{\|.*?\|\}', '', text, flags=re.DOTALL)

        # Xóa các dòng chỉ có ký tự đặc biệt còn sót
        text = re.sub(r'^\s*[\|\!]\s*.*$', '', text, flags=re.MULTILINE)

        # Chuẩn hóa khoảng trắng
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()

        return text

# Singleton instance
cleaner = TextCleaner()
