import re

def clean_text(text):
    """Remove |US| and special characters from the text, keeping only letters, numbers, and spaces."""
    text = text.replace("|US| ", "")
    return re.sub(r'[^a-zA-Z0-9\s]', '', text)

def normalize_name(name):
    """Normalize names by converting to lowercase, stripping spaces, and removing common suffixes."""
    name = name.lower().strip()
    common_terms = ["net", "network", "hd", "uhd", "tv", "channel", "east", "west", "USA"]
    for term in common_terms:
        name = name.replace(term, "")
    return re.sub(r'\s+', ' ', name)
