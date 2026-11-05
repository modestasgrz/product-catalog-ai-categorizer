import re

from fakes import DATA

URL = re.compile(r"https?://([^/\s\"',;<>]+)")
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")


def test_ac_26_mock_data_only() -> None:
    """AC-26: every URL host in data/ ends with .example and every e-mail domain ends with example.com."""
    files = [p for p in DATA.rglob("*") if p.is_file()]
    assert files, "data/ is empty or missing"
    for path in files:
        raw = path.read_bytes()
        text = raw.decode("cp1257") if "cp1257" in path.name else raw.decode("utf-8")
        for host in URL.findall(text):
            assert host.lower().endswith(".example"), f"{path.name}: {host}"
        for domain in EMAIL.findall(text):
            assert domain.lower().endswith("example.com"), f"{path.name}: {domain}"
