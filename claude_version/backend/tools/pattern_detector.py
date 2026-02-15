"""Pattern detection tool using pure Python heuristics (no LLM calls)."""

import json
import re

from langchain_core.tools import tool


@tool
def detect_patterns(message: str) -> str:
    """Detect suspicious patterns in a YouTube chat message using heuristics.

    Checks for URLs, ALL CAPS, repeated characters, emoji density, and
    abnormal message length. Returns a JSON string with boolean flags and counts.

    Args:
        message: The chat message text to analyze.

    Returns:
        JSON string with detected pattern flags.
    """
    # URL / link detection
    url_pattern = re.compile(
        r'https?://\S+|www\.\S+|[\w-]+\.(com|net|org|io|gg|tv|me|co)\b', re.IGNORECASE
    )
    urls_found = url_pattern.findall(message)
    url_count = len(re.findall(url_pattern, message))

    # ALL CAPS ratio
    alpha_chars = [c for c in message if c.isalpha()]
    if alpha_chars:
        caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
    else:
        caps_ratio = 0.0
    excessive_caps = caps_ratio > 0.7 and len(alpha_chars) >= 5

    # Repeated characters detection (3+ of the same char in a row)
    repeated_chars = bool(re.search(r'(.)\1{2,}', message))
    repeated_sequences = len(re.findall(r'(.)\1{2,}', message))

    # Emoji density
    emoji_pattern = re.compile(
        r'[\U0001F600-\U0001F64F'   # emoticons
        r'\U0001F300-\U0001F5FF'     # symbols & pictographs
        r'\U0001F680-\U0001F6FF'     # transport & map symbols
        r'\U0001F1E0-\U0001F1FF'     # flags
        r'\U00002702-\U000027B0'     # dingbats
        r'\U0000FE00-\U0000FE0F'     # variation selectors
        r'\U0001F900-\U0001F9FF'     # supplemental symbols
        r'\U0001FA00-\U0001FA6F'     # chess symbols
        r'\U0001FA70-\U0001FAFF'     # symbols extended-A
        r'\U00002600-\U000026FF]',   # misc symbols
        flags=re.UNICODE,
    )
    emoji_count = len(emoji_pattern.findall(message))
    msg_len = max(len(message), 1)
    emoji_density = emoji_count / msg_len
    excessive_emojis = emoji_density > 0.3 and emoji_count >= 3

    # Message length anomalies
    stripped = message.strip()
    too_short = len(stripped) < 3 and len(stripped) > 0
    too_long = len(stripped) > 300

    result = {
        "has_urls": url_count > 0,
        "url_count": url_count,
        "excessive_caps": excessive_caps,
        "caps_ratio": round(caps_ratio, 2),
        "repeated_chars": repeated_chars,
        "repeated_sequences_count": repeated_sequences,
        "excessive_emojis": excessive_emojis,
        "emoji_count": emoji_count,
        "emoji_density": round(emoji_density, 2),
        "too_short": too_short,
        "too_long": too_long,
        "message_length": len(stripped),
    }
    return json.dumps(result)
