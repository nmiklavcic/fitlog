from django.apps import AppConfig


class SocialConfig(AppConfig):
    name = "apps.social"
    label = "social"

    def ready(self):
        from . import signals  # noqa: F401  (connects the photo clean-up signal)
