from typing import Optional


def normalize_override_key(header_value: Optional[str]) -> Optional[str]:
    if header_value is None:
        return None
    if not isinstance(header_value, str):
        return None
    key = header_value.strip()
    return key or None
