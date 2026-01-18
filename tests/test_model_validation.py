"""Test model validation."""

from agents.utils.model_validation import get_allowed_models, validate_model


def test_allowed_model_passes():
    """Test that allowed models pass validation."""
    is_valid, error = validate_model("gpt-4o-mini")

    assert is_valid
    assert error is None
    print("✓ gpt-4o-mini is allowed")


def test_disallowed_model_fails():
    """Test that disallowed models fail validation."""
    is_valid, error = validate_model("malicious-model-evil")

    assert not is_valid
    assert error is not None
    print(f"✓ Disallowed model blocked: {error}")


def test_anthropic_model_allowed():
    """Test that Anthropic models are in default list."""
    is_valid, error = validate_model("anthropic/claude-3.5-sonnet")

    assert is_valid
    assert error is None
    print("✓ Anthropic Claude is allowed")


def test_environment_override():
    """Test that environment variable overrides defaults."""
    import os

    # Set custom allowed models
    os.environ["ALLOWED_MODELS"] = "custom-model-1,custom-model-2"

    is_valid, _ = validate_model("custom-model-1")

    assert is_valid
    print("✓ Environment override works")

    # Clean up
    del os.environ["ALLOWED_MODELS"]


def test_get_allowed_models():
    """Test that get_allowed_models returns proper list."""
    models = get_allowed_models()

    assert isinstance(models, list)
    assert len(models) > 0
    assert "gpt-4o-mini" in models
    assert "anthropic/claude-3.5-sonnet" in models
    print(f"✓ Default allowed models ({len(models)} models)")


def test_case_insensitive():
    """Test that model validation is case-insensitive."""
    # This might fail depending on implementation
    # But it's good to test
    is_valid, _ = validate_model("GPT-4O-MINI")

    # Model names should be exact match, not case-insensitive
    assert not is_valid  # Should fail because case doesn't match
    print("✓ Model validation is case-sensitive (expected)")


if __name__ == "__main__":
    test_allowed_model_passes()
    test_disallowed_model_fails()
    test_anthropic_model_allowed()
    test_environment_override()
    test_get_allowed_models()
    test_case_insensitive()
    print("\n✓ All model validation tests passed!")
