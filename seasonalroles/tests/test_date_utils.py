# pylint: disable=no-assert

from datetime import date, datetime, timezone

import pytest

from utilities.date_utils import DateUtil


def test_normalize_date():
    # Test with datetime
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert DateUtil.normalize_date(dt) == date(2024, 1, 1)

    # Test with date
    d = date(2024, 1, 1)
    assert DateUtil.normalize_date(d) == date(2024, 1, 1)

    # Test with invalid type
    with pytest.raises(TypeError):
        DateUtil.normalize_date("2024-01-01")


def test_str_to_date():
    # Test with YYYY-MM-DD format
    assert DateUtil.str_to_date("2024-01-01", "%Y-%m-%d") == date(2024, 1, 1)

    # Test with MM-DD format (current year)
    current_year = DateUtil.now().year
    assert DateUtil.str_to_date(f"{current_year}-05-05", "%Y-%m-%d") == date(
        current_year, 5, 5
    )

    # Test with invalid format
    with pytest.raises(
        ValueError, match="Date string 'invalid-date' does not match format"
    ):
        DateUtil.str_to_date("invalid-date", "%Y-%m-%d")


def test_now():
    # Test that now() returns a date object
    assert isinstance(DateUtil.now(), date)

    # Test that now() returns today's date
    today = datetime.now(timezone.utc).date()
    assert DateUtil.now() == today
