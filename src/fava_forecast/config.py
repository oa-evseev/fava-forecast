# config.py
import re

_RX_OPERATING_CURRENCY = re.compile(
    r'^\s*option\s+"operating_currency"\s+"([^"]+)"\s*$'
)

def detect_operating_currency_from_journal(journal_path: str, default_cur: str = "CRC") -> str:
    """Read operating_currency from journal options; fallback to default."""
    try:
        with open(journal_path, "r", encoding="utf-8") as f:
            for line in f:
                m = _RX_OPERATING_CURRENCY.match(line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return default_cur
