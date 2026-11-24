"""Shared keyword lists (English and Tamil) used by onboarding and the user agent."""
import re

CATEGORY_WORDS = [
    ("dentist", r"\bdent|teeth|tooth|பல்"),
    ("tailor", r"tailor|blouse|stitch|தையல்"),
    ("salon", r"salon|haircut|hair cut|parlour|parlor|facial|சலூன்"),
    ("clinic", r"clinic|doctor|கிளினிக்"),
    ("kirana", r"kirana|grocery|provision|மளிகை"),
    ("office", r"office|taluk|certificate|\bward\b|அலுவலகம்"),
]

LANGUAGE_WORDS = [
    ("Tamil", r"tamil|தமிழ்"),
    ("Hindi", r"hindi|हिंदी"),
    ("English", r"english"),
    ("Telugu", r"telugu"),
    ("Malayalam", r"malayalam"),
    ("Kannada", r"kannada"),
]


def detect_category(text):
    """Return the first matching category name, or None."""
    for name, pattern in CATEGORY_WORDS:
        if re.search(pattern, text, re.I):
            return name
    return None
