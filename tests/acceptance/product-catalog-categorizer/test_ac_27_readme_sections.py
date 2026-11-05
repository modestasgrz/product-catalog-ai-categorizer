from fakes import REPO


def test_ac_27_readme_sections() -> None:
    """AC-27: README has Usage, Output columns, How the answer key was made, Results."""
    lines = (REPO / "README.md").read_text(encoding="utf-8").splitlines()
    for heading in (
        "## Usage",
        "## Output columns",
        "## How the answer key was made",
        "## Results",
    ):
        assert heading in lines, heading
