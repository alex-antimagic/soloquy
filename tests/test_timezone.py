"""
Tests for timezone utility functions
"""
import pytest
from datetime import datetime
import pytz
from app.utils.timezone_utils import (
    convert_utc_to_user_tz,
    convert_user_tz_to_utc,
    format_datetime_for_user,
    get_timezone_offset
)


def test_utc_to_pacific_conversion():
    """Test converting UTC datetime to Pacific timezone"""
    # Create a UTC datetime
    utc_time = datetime(2024, 12, 1, 20, 0, 0)  # 8pm UTC
    utc_time = pytz.UTC.localize(utc_time)

    # Convert to Pacific
    pacific_time = convert_utc_to_user_tz(utc_time, 'America/Los_Angeles')

    # Should be 12pm PST (UTC-8 in winter)
    assert pacific_time.hour == 12
    assert pacific_time.minute == 0


def test_pacific_to_utc_conversion():
    """Test converting Pacific datetime to UTC"""
    # Create a Pacific datetime (noon PST)
    pacific_tz = pytz.timezone('America/Los_Angeles')
    pacific_time = pacific_tz.localize(datetime(2024, 12, 1, 12, 0, 0))

    # Convert to UTC
    utc_time = convert_user_tz_to_utc(pacific_time, 'America/Los_Angeles')

    # Should be 8pm UTC
    assert utc_time.hour == 20
    assert utc_time.minute == 0


def test_dst_transitions():
    """Test timezone conversion during DST transitions"""
    # Summer time (PDT = UTC-7)
    summer_utc = datetime(2024, 7, 1, 19, 0, 0)  # 7pm UTC in July
    summer_utc = pytz.UTC.localize(summer_utc)
    summer_pacific = convert_utc_to_user_tz(summer_utc, 'America/Los_Angeles')

    # Should be noon PDT (UTC-7 in summer)
    assert summer_pacific.hour == 12

    # Winter time (PST = UTC-8)
    winter_utc = datetime(2024, 12, 1, 20, 0, 0)  # 8pm UTC in December
    winter_utc = pytz.UTC.localize(winter_utc)
    winter_pacific = convert_utc_to_user_tz(winter_utc, 'America/Los_Angeles')

    # Should be noon PST (UTC-8 in winter)
    assert winter_pacific.hour == 12


def test_format_datetime_for_user():
    """Test formatting datetime for display"""
    utc_time = datetime(2024, 12, 1, 20, 0, 0)
    utc_time = pytz.UTC.localize(utc_time)

    # Format for Pacific timezone
    formatted = format_datetime_for_user(utc_time, 'America/Los_Angeles', '%I:%M %p %Z')

    # Should show PST timezone
    assert 'PST' in formatted or 'PDT' in formatted
    assert '12:00' in formatted  # noon in Pacific


def test_get_timezone_offset():
    """Test getting timezone offset string"""
    # Pacific timezone offset
    offset = get_timezone_offset('America/Los_Angeles')

    # Should be UTC-8:00 or UTC-7:00 depending on DST
    assert 'UTC' in offset
    assert '-' in offset


def test_none_datetime_handling():
    """Test handling of None datetimes"""
    result = convert_utc_to_user_tz(None, 'America/Los_Angeles')
    assert result is None

    result = convert_user_tz_to_utc(None, 'America/Los_Angeles')
    assert result is None

    result = format_datetime_for_user(None, 'America/Los_Angeles')
    assert result == ''


def test_invalid_timezone_handling():
    """Test handling of invalid timezone names"""
    utc_time = datetime(2024, 12, 1, 20, 0, 0)
    utc_time = pytz.UTC.localize(utc_time)

    # Should handle gracefully and return original
    result = convert_utc_to_user_tz(utc_time, 'Invalid/Timezone')
    assert result == utc_time


def test_naive_datetime_handling():
    """Test handling of naive (non-timezone-aware) datetimes"""
    # Create naive UTC datetime
    naive_utc = datetime(2024, 12, 1, 20, 0, 0)

    # Should localize and convert properly
    pacific_time = convert_utc_to_user_tz(naive_utc, 'America/Los_Angeles')

    assert pacific_time is not None
    assert pacific_time.hour == 12  # noon Pacific
