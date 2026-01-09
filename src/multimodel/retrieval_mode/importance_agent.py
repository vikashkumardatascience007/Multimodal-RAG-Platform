IMPORTANT_KEYWORDS = [
    "penalty",
    "termination",
    "liability",
    "fine",
    "compliance",
    "risk",
    "deadline",
    "breach",
    "payment",
    "interest",
    "tax"
]

def detect_important_information(text_chunks: list) -> bool:
    combined_text = " ".join(text_chunks).lower()
    return any(keyword in combined_text for keyword in IMPORTANT_KEYWORDS)
