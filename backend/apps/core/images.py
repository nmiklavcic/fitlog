"""Upload pipeline: validate -> deduplicate -> normalise -> resize -> WebP.

Instagram-style: the original is never kept. We store a 1080 px version for
the post view and a 320 px square crop for grids, both re-encoded as WebP
(typically ~95% smaller than a phone JPEG). Re-encoding also drops all
metadata (EXIF, GPS coordinates, camera serials), because nothing from the
source file is copied into the new one.
"""
import hashlib
import logging
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from .models import Photo

logger = logging.getLogger("liftlog.media")

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000  # ~40 MP; larger images are rejected (decompression-bomb protection)
FULL_SIZE = 1080
THUMB_SIZE = 320
WEBP_QUALITY = 80

# Pillow refuses to open anything above 2x this limit at all.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def _invalid(message):
    return ValidationError({"photo": [message]})


def _flatten(image):
    """Apply the EXIF orientation, then convert to RGB (transparent areas become white)."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _encode_webp(image):
    buffer = BytesIO()
    # No exif=/icc_profile=/xmp= arguments: the output carries no metadata.
    image.save(buffer, "WEBP", quality=WEBP_QUALITY, method=4)
    return buffer.getvalue()


def process_upload(uploaded_file):
    """Turn an uploaded file into a Photo (reusing an existing one for identical bytes)."""
    if uploaded_file is None:
        raise _invalid("Choose a photo to upload.")
    if uploaded_file.size > settings.MAX_UPLOAD_BYTES:
        raise _invalid(f"The photo must be {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.")

    data = uploaded_file.read()
    digest = hashlib.sha256(data).hexdigest()
    existing = Photo.objects.filter(sha256=digest).first()
    if existing:
        return existing

    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise _invalid("Only JPEG, PNG and WebP images are supported.")
            if source.width * source.height > MAX_PIXELS:
                raise _invalid("This image is too large.")
            source.load()  # fully decode now so corrupt/truncated files fail here
            image = _flatten(source)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise _invalid("This file isn't a valid JPEG, PNG or WebP image.")

    full = image.copy()
    full.thumbnail((FULL_SIZE, FULL_SIZE), Image.Resampling.LANCZOS)  # only shrinks, never enlarges
    thumb = ImageOps.fit(image, (THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)

    photo = Photo(sha256=digest, width=full.width, height=full.height)
    for variant, rendered in (("1080", full), ("320", thumb)):
        path = photo.path(variant)
        if default_storage.exists(path):  # leftover from an interrupted upload
            default_storage.delete(path)
        default_storage.save(path, ContentFile(_encode_webp(rendered)))
    try:
        with transaction.atomic():
            photo.save()
    except IntegrityError:  # the same file was uploaded concurrently
        return Photo.objects.get(sha256=digest)
    logger.info(
        "photo_stored",
        extra={"event": "photo_stored", "sha256": digest[:12], "bytes_in": len(data), "width": full.width},
    )
    return photo


def delete_photo_files(photo):
    for variant in Photo.VARIANTS:
        path = photo.path(variant)
        if default_storage.exists(path):
            default_storage.delete(path)


def delete_photo_if_unused(photo_id):
    """Remove a Photo and its files once no post or avatar points at it any more."""
    photo = Photo.objects.filter(pk=photo_id, posts__isnull=True, avatar_of__isnull=True).first()
    if photo is None:
        return False
    delete_photo_files(photo)
    photo.delete()
    return True
