from articles import Article


def test_slug():
    assert Article("Hello, World!", "").slug == "hello-world"


def test_slug_strips_accents():
    assert Article("Café Déjà Vu", "").slug == "cafe-deja-vu"


def test_preview_truncates():
    body = "word " * 40
    preview = Article("t", body).preview(20)
    assert len(preview) <= 20
    assert preview.endswith("...")
