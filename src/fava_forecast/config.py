# config.py
import re


# Kept for potential reuse; not strictly required by budgets.py (it has its own rx)
BUDGET_RE = re.compile(
    r'^\s*(\d{4}-\d{2}-\d{2})\s+custom\s+"budget"\s+"([^"]+)"\s+"(weekly|monthly)"\s+([\d_]+(?:\.\d+)?)\s+([A-Z]{3,5})'
)


def detect_operating_currency_from_journal(journal_path: str, default_cur: str = "CRC") -> str:
    """Read operating_currency from journal options; fallback to default."""
    try:
        with open(journal_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith('option "operating_currency"'):
                    return line.split()[-1].strip('"')
    except Exception:
        pass
    return default_cur

