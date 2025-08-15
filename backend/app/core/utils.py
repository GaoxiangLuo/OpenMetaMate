import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_expected_key(item_name: str) -> str:
    """Convert coding scheme item name to expected flattened JSON key"""
    if not item_name:
        logger.warning("⚠️ Empty item name provided")
        return ""

    parts = item_name.split("/")
    converted_parts = []
    for part in parts:
        # Handle edge cases in part names
        part = part.strip()
        if not part:
            logger.debug("🔧 Skipping empty part in item name")
            continue

        # Convert to lowercase and replace spaces with underscores
        converted_part = part.lower().replace(" ", "_")
        # Remove any special characters that might cause issues
        converted_part = "".join(c if c.isalnum() or c == "_" else "_" for c in converted_part)
        # Clean up multiple underscores
        converted_part = "_".join(p for p in converted_part.split("_") if p)

        if converted_part:
            converted_parts.append(converted_part)

    result = "/".join(converted_parts)
    logger.debug(f"🔄 Converted '{item_name}' to '{result}'")
    return result


def is_not_found_value(value: Any) -> bool:
    """Check if value indicates 'not found'"""
    if value is None:
        logger.debug("🔍 Value is None, marking as not found")
        return True

    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in settings.NOT_FOUND_STRINGS:
            logger.debug(f"🔍 String value '{stripped}' matches not-found pattern")
            return True
        # Also check for variations
        if stripped in ["unknown", "not specified", "not reported", "nr", "missing"]:
            logger.debug(f"🔍 String value '{stripped}' is a not-found variation")
            return True

    if isinstance(value, (int, float)):
        if value == settings.NOT_FOUND_NUMERIC_VALUE:
            logger.debug(f"🔍 Numeric value {value} matches not-found value")
            return True
        # Check for other common "not found" numeric values
        if value in [-999, -9999, -1]:
            logger.debug(f"🔍 Numeric value {value} is a common not-found indicator")
            return True

    if isinstance(value, list) and len(value) == 0:
        logger.debug("🔍 Empty list, marking as not found")
        return True

    if isinstance(value, dict) and len(value) == 0:
        logger.debug("🔍 Empty dict, marking as not found")
        return True

    return False
