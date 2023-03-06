import cogs.pings


def test_checkASCII():
    assert cogs.pings.check_ascii("Hello World")


def test_checkASCII_false():
    assert not cogs.pings.check_ascii("Héllo World")


def test_sanitize_empty():
    assert cogs.pings.sanitize_check("") is not None


def test_sanitize_mention():
    assert cogs.pings.sanitize_check("<@96018174163570688>") is not None


def test_sanitize_long():
    assert cogs.pings.sanitize_check("This is a long string which exceeds twenty characters") is not None


def test_sanitize_emote():
    assert cogs.pings.sanitize_check("Hello :eyes: world") is not None


def test_sanitize_nonASCII():
    assert cogs.pings.sanitize_check("Héllo World") is not None


def test_sanitize_comma():
    assert cogs.pings.sanitize_check("Hello, World") is not None
