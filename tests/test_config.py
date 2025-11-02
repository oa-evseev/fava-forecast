import fava_forecast.config as cfg


def test_detect_operating_currency_found(tmp_path):
    p = tmp_path / "main.bean"
    p.write_text('  option  "operating_currency"   "USD"\n', encoding="utf-8")
    assert cfg.detect_operating_currency_from_journal(str(p), default_cur="CRC") == "USD"


def test_detect_operating_currency_tabs_and_spaces(tmp_path):
    p = tmp_path / "main.bean"
    p.write_text('\toption\t"operating_currency"\t"EUR"\t\n', encoding="utf-8")
    assert cfg.detect_operating_currency_from_journal(str(p), default_cur="CRC") == "EUR"


def test_detect_operating_currency_ignores_comments(tmp_path):
    p = tmp_path / "main.bean"
    p.write_text(
        "\n".join([
            '; option "operating_currency" "ZZZ"',
            '* option "operating_currency" "QQQ"',
            '# option "operating_currency" "WWW"',
            'option "operating_currency" "USD"',
        ]),
        encoding="utf-8",
    )
    assert cfg.detect_operating_currency_from_journal(str(p), default_cur="CRC") == "USD"


def test_detect_operating_currency_no_option_returns_default(tmp_path):
    p = tmp_path / "main.bean"
    p.write_text('; no operating currency here\n', encoding="utf-8")
    assert cfg.detect_operating_currency_from_journal(str(p), default_cur="CRC") == "CRC"


def test_detect_operating_currency_missing_file_returns_default():
    assert cfg.detect_operating_currency_from_journal("absent.bean", default_cur="CRC") == "CRC"


def test_detect_operating_currency_first_match_wins(tmp_path):
    p = tmp_path / "main.bean"
    p.write_text(
        '\n'.join([
            'option "operating_currency" "USD"',
            'option "operating_currency" "EUR"',
        ]),
        encoding="utf-8"
    )
    # Function returns the first occurrence
    assert cfg.detect_operating_currency_from_journal(str(p), default_cur="CRC") == "USD"
