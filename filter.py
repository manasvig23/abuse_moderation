def load_abusive(filepath="abusive_words.txt"):
    with open(filepath, "r") as f:
        return [line.strip().lower() for line in f.readlines()]

abusive_words = load_abusive()

def is_abusive(text: str) -> int:
    text_lower = text.lower()
    return any(word in text_lower for word in abusive_words)
