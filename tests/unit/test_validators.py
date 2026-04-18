import pytest

from hub.validators import validate_slug, validate_version_name, SLUG_RE


class TestSlug:
    @pytest.mark.parametrize("s", ["covid-jhu", "a", "imdb-reviews", "x1", "dataset-2020-01"])
    def test_valid(self, s: str) -> None:
        assert validate_slug(s) == s

    @pytest.mark.parametrize(
        "s",
        [
            "",                      # empty
            "-leading-dash",         # starts with dash
            "UPPER",                 # uppercase
            "has space",             # space
            "has_underscore",        # underscore
            "has.dot",               # dot
            "has/slash",             # slash
            "a" * 64,                # too long (max 63)
            "shell$injection",       # shell metachar
            "; rm -rf /",            # blatant injection
        ],
    )
    def test_invalid(self, s: str) -> None:
        with pytest.raises(ValueError):
            validate_slug(s)

    def test_regex_is_canonical(self) -> None:
        assert SLUG_RE.pattern == r"^[a-z0-9][a-z0-9-]{0,62}$"


class TestVersionName:
    def test_same_rules_as_slug(self) -> None:
        assert validate_version_name("cleaned-2026-04") == "cleaned-2026-04"
        with pytest.raises(ValueError):
            validate_version_name("Has Upper")
