"""Content moderation for LLM outputs."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class ContentModerationError(Exception):
    """Exception raised when content moderation fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Content moderation failed: {reason}")


class ContentModerator:
    """Moderates LLM output for harmful content."""

    PATTERNS = {
        "hate_speech": [
            r"(?i)\b(nigger|kike|faggot|chink|spic|wetback)\b",
            r"(?i)(kill|murder|exterminate|eradicate).*(all|every).*(?:jews|blacks|gays|muslims)",
        ],
        "violence": [
            r"(?i)(how to|instructions).*(kill|murder|assassinate|bomb|explode|shoot)",
            r"(?i)step.by.step.guide.*(murder|kill|assassinate)",
        ],
        "self_harm": [
            r"(?i)how to (commit|carry out).*(suicide|kill myself)",
            r"(?i)best way to (end|take).*(my life|it all)",
        ],
        "sexual_content": [
            r"(?i)(explicit|nsfw|pornographic|erotic).*(content|images|videos)",
        ],
    }

    def __init__(self, enabled: bool = True) -> None:
        """
        Initialize content moderator.

        Args:
            enabled: Whether moderation is enabled (can be disabled via env var).
        """
        self.enabled = enabled

    def _check_pattern(self, text: str, category: str, pattern: str) -> bool:
        """
        Check if text matches a harmful pattern.

        Args:
            text: Text to check.
            category: Pattern category for logging.
            pattern: Regex pattern to match.

        Returns:
            True if pattern matches, False otherwise.
        """
        try:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(
                    f"Content moderation triggered (category={category}): pattern matched"
                )
                return True
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
        return False

    def moderate(self, content: str) -> tuple[bool, str | None]:
        """
        Moderate content for harmful patterns.

        Args:
            content: LLM output to moderate.

        Returns:
            Tuple of (is_safe, reason).
        """
        if not self.enabled:
            return True, None

        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if self._check_pattern(content, category, pattern):
                    reason = f"Content matched {category} policy"
                    return False, reason

        return True, None

    def moderate_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Moderate all string values in a dictionary.

        Args:
            data: Dictionary with potential LLM outputs.

        Returns:
            Dictionary with moderation errors added if found.
        """
        result = data.copy()

        for key, value in result.items():
            if isinstance(value, str):
                is_safe, reason = self.moderate(value)
                if not is_safe:
                    result[key] = {
                        "_content": value,
                        "_moderation_blocked": True,
                        "_moderation_reason": reason,
                    }
                    logger.warning(f"Blocked content in field '{key}': {reason}")

        return result
