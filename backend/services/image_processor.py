import base64
import io
import logging
from typing import Dict, Optional

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Safety limits to prevent OOM
MAX_IMAGE_DIMENSION = 4096  # max width/height in pixels
MAX_IMAGE_PIXELS = 4096 * 4096  # ~16.7M pixels
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageProcessor:
    """Image validation, preprocessing, and local filter application."""

    def validate_and_prepare(self, image_bytes: bytes) -> Dict:
        """Validate image safety and prepare for API submission.

        Returns:
            Dict with 'base64' (str) and 'dimensions' (dict).

        Raises:
            ValueError: If image fails validation.
        """
        # Size check
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Image too large: {len(image_bytes) // 1024}KB "
                f"(max {MAX_IMAGE_SIZE_BYTES // 1024 // 1024}MB)"
            )

        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"Cannot decode image: {str(e)}")

        # Format check
        if img.format and img.format not in ALLOWED_FORMATS:
            raise ValueError(
                f"Unsupported format: {img.format}. Allowed: {', '.join(ALLOWED_FORMATS)}"
            )

        # Dimension check
        width, height = img.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise ValueError(
                f"Image too large: {width}x{height}. Max dimension: {MAX_IMAGE_DIMENSION}px"
            )
        if width * height > MAX_IMAGE_PIXELS:
            raise ValueError(
                f"Too many pixels: {width * height:,}. Max: {MAX_IMAGE_PIXELS:,}"
            )

        # Normalize to RGB if necessary
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Re-encode as JPEG for API submission
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=92)
        b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        logger.info(
            "Image validated: %dx%d %s -> JPEG %dKB",
            width, height, img.format, len(buffer.getvalue()) // 1024,
        )

        return {
            "base64": b64_data,
            "dimensions": {"width": width, "height": height},
        }

    def apply_filters(
        self,
        image_bytes: bytes,
        brightness: Optional[float] = None,
        contrast: Optional[float] = None,
        saturation: Optional[float] = None,
        sharpness: Optional[float] = None,
        blur: Optional[float] = None,
        rotate: Optional[int] = None,
        flip_h: Optional[bool] = None,
        flip_v: Optional[bool] = None,
        filter_type: Optional[str] = None,
    ) -> str:
        """Apply local PIL filters to image.

        Returns:
            Base64-encoded result image (JPEG format for smaller size and broad compatibility).
        """
        img = Image.open(io.BytesIO(image_bytes))

        # Track if image has alpha channel (transparency)
        has_alpha = img.mode in ("RGBA", "LA", "PA")

        # Ensure RGB mode for consistent processing
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Preset filters (applied first)
        if filter_type:
            img = self._apply_preset_filter(img, filter_type)

        # Individual adjustments
        if brightness is not None and brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(brightness)

        if contrast is not None and contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast)

        if saturation is not None and saturation != 1.0:
            img = ImageEnhance.Color(img).enhance(saturation)

        if sharpness is not None and sharpness != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(sharpness)

        if blur is not None and blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))

        if rotate is not None and rotate != 0:
            img = img.rotate(rotate, expand=True)

        if flip_h:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        if flip_v:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

        # Encode result as JPEG (smaller than PNG, universal compatibility)
        buffer = io.BytesIO()
        if has_alpha and img.mode == "RGBA":
            # JPEG doesn't support alpha — composite on white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            background.save(buffer, format="JPEG", quality=92)
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buffer, format="JPEG", quality=92)

        result_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        logger.info("Filter applied: filter_type=%s, output=%dKB", filter_type, len(buffer.getvalue()) // 1024)
        return result_b64

    @staticmethod
    def _apply_preset_filter(img: "Image.Image", filter_type: str) -> "Image.Image":
        """Apply a named preset filter."""
        if filter_type == "vintage":
            # Warm sepia-like tone
            img = ImageEnhance.Color(img).enhance(0.7)
            img = ImageEnhance.Contrast(img).enhance(1.1)
            # Apply slight sepia overlay
            sepia = Image.new("RGB", img.size, (255, 235, 205))
            img = Image.blend(img.convert("RGB"), sepia, alpha=0.2)
        elif filter_type == "bw":
            img = img.convert("L").convert("RGB")
        elif filter_type == "sepia":
            img = img.convert("RGB")
            sepia = Image.new("RGB", img.size, (255, 235, 205))
            img = Image.blend(img, sepia, alpha=0.4)
        elif filter_type == "edge":
            img = img.filter(ImageFilter.FIND_EDGES)
        elif filter_type == "sharpen":
            img = img.filter(ImageFilter.SHARPEN)
        else:
            logger.warning("Unknown preset filter: %s", filter_type)
        return img
