"""Basic tests to verify the testing setup."""

import pytest


def test_basic_functionality() -> None:
    """Test that basic functionality works."""
    assert True


def test_math_operations() -> None:
    """Test basic math operations."""
    assert 2 + 2 == 4
    assert 3 * 3 == 9
    assert 10 - 5 == 5


@pytest.mark.unit
def test_unit_marker() -> None:
    """Test that unit markers work."""
    assert True
