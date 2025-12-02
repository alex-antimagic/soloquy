"""
Timezone utility functions
"""
from datetime import datetime
import pytz


# Common timezones to show in UI (grouped by region)
COMMON_TIMEZONES = [
    # US
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Phoenix',
    'America/Anchorage',
    'Pacific/Honolulu',

    # Canada
    'America/Toronto',
    'America/Vancouver',

    # Europe
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Europe/Rome',
    'Europe/Madrid',

    # Asia
    'Asia/Tokyo',
    'Asia/Shanghai',
    'Asia/Hong_Kong',
    'Asia/Singapore',
    'Asia/Dubai',
    'Asia/Kolkata',

    # Australia
    'Australia/Sydney',
    'Australia/Melbourne',

    # Other
    'UTC',
]


def get_timezone_offset(tz_name):
    """Get current UTC offset for a timezone (e.g., 'UTC-8:00')"""
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        offset = now.strftime('%z')
        return f"UTC{offset[:3]}:{offset[3:]}"
    except:
        return "UTC+0:00"


def convert_utc_to_user_tz(utc_datetime, user_timezone):
    """Convert UTC datetime to user's timezone"""
    if not utc_datetime:
        return None

    try:
        # Ensure UTC timezone awareness
        if utc_datetime.tzinfo is None:
            utc_datetime = pytz.UTC.localize(utc_datetime)

        # Convert to user timezone
        user_tz = pytz.timezone(user_timezone)
        return utc_datetime.astimezone(user_tz)
    except Exception as e:
        print(f"Error converting timezone: {e}")
        return utc_datetime


def convert_user_tz_to_utc(local_datetime, user_timezone):
    """Convert user's local datetime to UTC"""
    if not local_datetime:
        return None

    try:
        user_tz = pytz.timezone(user_timezone)

        # If naive datetime, localize it
        if local_datetime.tzinfo is None:
            local_datetime = user_tz.localize(local_datetime)

        # Convert to UTC
        return local_datetime.astimezone(pytz.UTC)
    except Exception as e:
        print(f"Error converting to UTC: {e}")
        return local_datetime


def format_datetime_for_user(utc_datetime, user_timezone, format_str='%Y-%m-%d %I:%M %p %Z'):
    """Format UTC datetime for display in user's timezone"""
    if not utc_datetime:
        return ''

    local_dt = convert_utc_to_user_tz(utc_datetime, user_timezone)
    if local_dt:
        return local_dt.strftime(format_str)
    return utc_datetime.strftime(format_str)
