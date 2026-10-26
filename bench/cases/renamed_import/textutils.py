import re
import unicodedata


def slugify_text(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def truncate(value, length=80, suffix="..."):
    if len(value) <= length:
        return value
    return value[: length - len(suffix)].rstrip() + suffix
