"""Masquage des données personnelles et bancaires avant tout envoi vers un fournisseur d'IA externe."""
import re

PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("RIB", re.compile(r"\b\d{20}\b")),                                   # RIB algérien (20 chiffres)
    ("NIF", re.compile(r"\b\d{15}\b")),                                   # NIF (15 chiffres)
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b")),
    ("TEL", re.compile(r"(?:\+213|00213|\b0)[\s.-]?[5-7](?:[\s.-]?\d{2}){4}\b")),
    ("TEL", re.compile(r"(?:\+213|00213|\b0)[\s.-]?[2-4]\d(?:[\s.-]?\d{2}){3}\b")),
]


def redact(text: str) -> tuple[str, int]:
    count = 0
    for label, rx in PATTERNS:
        text, n = rx.subn(f"[{label} masqué]", text)
        count += n
    return text, count
