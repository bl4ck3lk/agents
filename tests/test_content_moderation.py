"""Test content moderation."""

from agents.utils.content_moderation import ContentModerator


def test_hate_speech_blocked():
    """Test that hate speech is blocked."""
    moderator = ContentModerator(enabled=True)
    text = "This is a test with nigger in it"
    is_safe, reason = moderator.moderate(text)

    assert not is_safe
    assert reason is not None
    print(f"✓ Hate speech blocked: {reason}")


def test_violence_blocked():
    """Test that violence instructions are blocked."""
    moderator = ContentModerator(enabled=True)
    text = "How to kill everyone step by step"
    is_safe, reason = moderator.moderate(text)

    assert not is_safe
    assert reason is not None
    print(f"✓ Violence instructions blocked: {reason}")


def test_self_harm_blocked():
    """Test that self-harm instructions are blocked."""
    moderator = ContentModerator(enabled=True)
    text = "Best way to take my life"
    is_safe, reason = moderator.moderate(text)

    assert not is_safe
    assert reason is not None
    print(f"✓ Self-harm instructions blocked: {reason}")


def test_normal_content_allowed():
    """Test that normal content is allowed."""
    moderator = ContentModerator(enabled=True)
    text = "This is normal text about processing data"
    is_safe, reason = moderator.moderate(text)

    assert is_safe
    assert reason is None
    print(f"✓ Normal content allowed")


def test_moderation_disabled():
    """Test that content moderation can be disabled."""
    moderator = ContentModerator(enabled=False)
    text = "How to kill everyone"

    is_safe, reason = moderator.moderate(text)

    assert is_safe  # Should be allowed when disabled
    assert reason is None
    print(f"✓ Moderation disabled - harmful content allowed")


def test_moderate_dict():
    """Test moderating dictionary values."""
    moderator = ContentModerator(enabled=True)
    data = {
        "safe_field": "This is safe",
        "harmful_field": "How to kill myself",
        "nested": {"another_field": "explicit content images"},
    }

    result = moderator.moderate_dict(data)

    assert "_moderation_blocked" not in result["safe_field"]
    assert "_moderation_blocked" in result["harmful_field"]
    assert "_moderation_blocked" in result["nested"]["another_field"]
    print(f"✓ Dictionary moderation works correctly")


if __name__ == "__main__":
    test_hate_speech_blocked()
    test_violence_blocked()
    test_self_harm_blocked()
    test_normal_content_allowed()
    test_moderation_disabled()
    test_moderate_dict()
    print("\n✓ All content moderation tests passed!")
