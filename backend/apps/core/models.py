from django.db import models


class Photo(models.Model):
    """A processed image, stored once per unique upload (content-addressed by SHA-256).

    Files on disk: photos/<first 2 hash chars>/<sha256>/1080.webp and 320.webp.
    Several posts/avatars may point at the same Photo when identical files are uploaded.
    """

    VARIANTS = ("1080", "320")

    sha256 = models.CharField(max_length=64, unique=True)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.sha256[:12]

    @property
    def directory(self):
        return f"photos/{self.sha256[:2]}/{self.sha256}"

    def path(self, variant):
        return f"{self.directory}/{variant}.webp"
