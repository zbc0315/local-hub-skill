import re

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def validate_slug(s: str) -> str:
    if not isinstance(s, str) or not SLUG_RE.match(s):
        raise ValueError(
            f"invalid slug {s!r}: must match {SLUG_RE.pattern}"
        )
    return s


def validate_version_name(s: str) -> str:
    try:
        return validate_slug(s)
    except ValueError as e:
        raise ValueError(str(e).replace("slug", "version name")) from None
