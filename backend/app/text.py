def tr_upper(s: str) -> str:
    """Türkçe büyük harf: 'i' -> 'İ', 'ı' -> 'I' (Python'un upper()'ı bunu yapmaz)."""
    return s.replace("i", "İ").replace("ı", "I").upper()
