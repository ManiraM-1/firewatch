from textutils import slugify, truncate


class Article:
    def __init__(self, title, body):
        self.title = title
        self.body = body

    @property
    def slug(self):
        return slugify(self.title)

    def preview(self, length=60):
        return truncate(self.body, length)
