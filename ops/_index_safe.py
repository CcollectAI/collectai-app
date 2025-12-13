import io
from PIL import Image, UnidentifiedImageError, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

def safe_load_rgb(data: bytes):
    """Return RGB PIL image or None if bytes are not a valid image."""
    if not data or len(data) < 12:
        return None
    try:
        im = Image.open(io.BytesIO(data))
        im.verify()  # header check
        im = Image.open(io.BytesIO(data)).convert("RGB")
        return im
    except UnidentifiedImageError:
        return None
    except Exception:
        return None
