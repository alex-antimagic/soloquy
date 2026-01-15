# Timezone Support Documentation

## Overview

worklead implements comprehensive timezone support to ensure all users see times in their local timezone, regardless of where they're located. This document explains the architecture, conventions, and best practices for working with timezones in the application.

## Architecture

### Storage Layer (Database)

**Convention:** All datetime fields are stored as **naive UTC** datetimes in PostgreSQL.

```python
# ✅ Correct - Store as naive UTC
user.last_seen = datetime.utcnow()
task.due_date = datetime.utcnow()
message.created_at = datetime.utcnow()

# ❌ Wrong - Don't use local time
user.last_seen = datetime.now()  # This is local server time!

# ❌ Wrong - Don't store timezone-aware datetimes
user.last_seen = datetime.now(pytz.timezone('America/Los_Angeles'))
```

**Why naive UTC?**
- Simplicity: No timezone information stored in database
- Consistency: All times are in the same reference frame
- Portability: Works across all timezones
- Performance: No timezone conversion overhead in queries

### Display Layer (Templates & APIs)

**Convention:** Convert UTC to user's timezone at the display boundary.

#### In Templates

Use the `|user_timezone` filter:

```html
<!-- ✅ Correct - Convert to user's timezone -->
{{ message.created_at|user_timezone('%I:%M %p %Z') }}
<!-- Output: "3:45 PM PST" -->

<!-- ❌ Wrong - Shows raw UTC -->
{{ message.created_at.strftime('%I:%M %p') }}
<!-- Output: "11:45 PM" (incorrect for PST user) -->
```

#### In Python Code

Use the `format_datetime_for_user()` utility:

```python
from app.utils.timezone_utils import format_datetime_for_user

# Convert for display
formatted = format_datetime_for_user(
    utc_datetime=task.due_date,
    user_timezone=current_user.timezone_preference,
    format_str='%b %d, %I:%M %p %Z'
)
# Returns: "Dec 01, 3:45 PM PST"
```

### Input Layer (User Input)

**Convention:** Convert from user's timezone to UTC before storing.

```python
from app.utils.timezone_utils import convert_user_tz_to_utc

# User provides local time
user_input_time = datetime(2024, 12, 1, 14, 0, 0)  # 2pm in user's TZ

# Convert to UTC before storing
utc_time = convert_user_tz_to_utc(user_input_time, current_user.timezone_preference)
task.due_date = utc_time.replace(tzinfo=None)  # Store as naive UTC
```

## User Timezone Preference

### Storage

Each user has a `timezone_preference` field storing an IANA timezone name:

```python
user.timezone_preference = 'America/Los_Angeles'  # PST/PDT
user.timezone_preference = 'America/New_York'     # EST/EDT
user.timezone_preference = 'Europe/London'        # GMT/BST
user.timezone_preference = 'UTC'                  # Default
```

### Auto-Detection

On first login or registration, the browser auto-detects the user's timezone:

```javascript
// Detects timezone using JavaScript
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
// Returns: "America/Los_Angeles"
```

This value is sent to the server and saved to `user.timezone_preference` if the user is still using the UTC default.

### Manual Override

Users can change their timezone in **Account Settings** → **Timezone**:
- Dropdown with 23 common timezones
- Changes take effect immediately
- Affects all time displays and calendar operations

## AI Agent Context

AI agents receive timezone context in their system prompt:

```
=== TIMEZONE CONTEXT ===
User's timezone: America/Los_Angeles
Current time in user's timezone: 2024-12-01 09:30:00 PST
IMPORTANT: When creating calendar events or displaying times, always:
1. Show times in America/Los_Angeles format (include timezone abbreviation like 'PST', 'EST', etc.)
2. Convert user's local time inputs to UTC for API calls
3. Display 'Creating calendar event at 2pm PST' to confirm timezone
```

This enables agents to:
- Interpret relative times correctly ("tomorrow at 2pm" = 2pm PST, not UTC)
- Display times with timezone abbreviations
- Confirm timezone when creating calendar events

## Outlook Calendar Integration

### Creating Events

When AI agents create calendar events, they:

1. **Receive user's local time** from conversation (e.g., "2pm")
2. **Convert to UTC** before calling the API
3. **Send UTC time** to Microsoft Graph API with `timezone: 'UTC'`
4. **Display confirmation** in user's timezone (e.g., "Event created at 2pm PST")

```python
# In outlook_service.py
event_data = {
    'subject': 'Meeting',
    'start': {
        'dateTime': '2024-12-01T22:00:00',  # UTC (converted from 2pm PST)
        'timeZone': 'UTC'
    },
    'end': {
        'dateTime': '2024-12-01T23:00:00',  # UTC
        'timeZone': 'UTC'
    }
}
```

### Reading Events

When fetching calendar events, times are:
1. Received from Microsoft Graph in UTC
2. Converted to user's timezone for display
3. Shown with timezone abbreviation

## Developer Guidelines

### Adding New Datetime Fields

When adding new datetime fields to models:

```python
class NewModel(db.Model):
    # ✅ Correct - Naive UTC default
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    scheduled_for = db.Column(db.DateTime)

    # ❌ Wrong - Don't use datetime.now()
    created_at = db.Column(db.DateTime, default=datetime.now)
```

### Displaying Times in Templates

Always use the `|user_timezone` filter:

```html
<!-- Messages -->
<span>{{ message.created_at|user_timezone('%I:%M %p %Z') }}</span>

<!-- Tasks -->
<p>Due: {{ task.due_date|user_timezone('%b %d, %Y at %I:%M %p %Z') }}</p>

<!-- Activities -->
<time>{{ activity.scheduled_at|user_timezone }}</time>
```

### API Responses

When returning datetime in JSON APIs:

```python
# ✅ Correct - Format in user's timezone
from app.utils.timezone_utils import format_datetime_for_user

return {
    'created_at': format_datetime_for_user(
        item.created_at,
        current_user.timezone_preference,
        '%Y-%m-%dT%H:%M:%S'
    ),
    'timezone': current_user.timezone_preference
}

# ❌ Wrong - Don't return raw UTC without context
return {
    'created_at': item.created_at.isoformat()  # Ambiguous!
}
```

### Background Jobs

Long-running tasks format times in user's timezone for notifications:

```python
from app.utils.timezone_utils import format_datetime_for_user

# Format completion time for notification
formatted_time = format_datetime_for_user(
    task.completed_at,
    user.timezone_preference,
    '%b %d at %I:%M %p %Z'
)
notification = f"Task completed on {formatted_time}"
```

## Utility Functions

### `convert_utc_to_user_tz(utc_datetime, user_timezone)`

Converts naive UTC datetime to user's timezone.

```python
from app.utils.timezone_utils import convert_utc_to_user_tz

utc_time = datetime(2024, 12, 1, 20, 0, 0)  # 8pm UTC
pst_time = convert_utc_to_user_tz(utc_time, 'America/Los_Angeles')
# Result: 2024-12-01 12:00:00 PST (noon Pacific)
```

### `convert_user_tz_to_utc(local_datetime, user_timezone)`

Converts user's local time to UTC.

```python
from app.utils.timezone_utils import convert_user_tz_to_utc

pst_time = datetime(2024, 12, 1, 14, 0, 0)  # 2pm PST
utc_time = convert_user_tz_to_utc(pst_time, 'America/Los_Angeles')
# Result: 2024-12-01 22:00:00 UTC
```

### `format_datetime_for_user(utc_datetime, user_timezone, format_str)`

Formats UTC datetime for display in user's timezone.

```python
from app.utils.timezone_utils import format_datetime_for_user

formatted = format_datetime_for_user(
    datetime.utcnow(),
    'America/Los_Angeles',
    '%I:%M %p %Z'
)
# Result: "03:45 PM PST"
```

### `get_timezone_offset(tz_name)`

Gets the current UTC offset for a timezone.

```python
from app.utils.timezone_utils import get_timezone_offset

offset = get_timezone_offset('America/Los_Angeles')
# Result: "UTC-8:00" (winter) or "UTC-7:00" (summer)
```

## DST (Daylight Saving Time) Handling

The `pytz` library automatically handles DST transitions:

- **PST (Pacific Standard Time):** UTC-8 (November - March)
- **PDT (Pacific Daylight Time):** UTC-7 (March - November)

Times are automatically adjusted during transitions. No special handling required.

## Testing

### Unit Tests

See `tests/test_timezone.py` for timezone utility tests:
- UTC ↔ Pacific conversion
- DST transition handling
- None/invalid input handling
- Format string variations

### Integration Tests

See `tests/test_timezone_integration.py` for full-stack tests:
- User timezone preference storage
- Template filter conversion
- Message timestamp display
- Auto-detection on registration
- Settings page updates

### Running Tests

```bash
# Run all timezone tests
pytest tests/test_timezone.py tests/test_timezone_integration.py

# Run with coverage
pytest --cov=app.utils.timezone_utils tests/test_timezone.py
```

## Common Pitfalls

### ❌ Using `datetime.now()`

```python
# WRONG - Uses local server time
task.due_date = datetime.now()
```

**Problem:** Server might be in different timezone than user.

**Solution:** Always use `datetime.utcnow()`.

### ❌ Not Using Template Filter

```html
<!-- WRONG - Shows UTC to user -->
{{ message.created_at.strftime('%I:%M %p') }}
```

**Problem:** Displays UTC time, confusing for non-UTC users.

**Solution:** Use `|user_timezone` filter.

### ❌ Storing Timezone-Aware Datetimes

```python
# WRONG - Storing timezone info in database
from datetime import timezone
task.due_date = datetime.now(timezone.utc)
```

**Problem:** Adds unnecessary complexity, breaks queries.

**Solution:** Store naive UTC, convert at boundaries.

### ❌ Forgetting AI Agent Context

When adding new calendar/time features, ensure AI agents have timezone context in their system prompt.

## Migration Guide

### For Existing Code

If you find code using `datetime.now()`:

1. **Change to `datetime.utcnow()`**
   ```python
   # Before
   timestamp = datetime.now()

   # After
   timestamp = datetime.utcnow()
   ```

2. **Add template filters to displays**
   ```html
   <!-- Before -->
   {{ task.due_date.strftime('%b %d, %Y') }}

   <!-- After -->
   {{ task.due_date|user_timezone('%b %d, %Y %Z') }}
   ```

3. **Update API responses**
   ```python
   # Before
   'created_at': item.created_at.isoformat()

   # After
   'created_at': format_datetime_for_user(item.created_at, user.timezone_preference)
   ```

## Support

### User Issues

If users report incorrect times:

1. Check their timezone setting in Account Settings
2. Verify times are stored as UTC in database
3. Confirm templates use `|user_timezone` filter
4. Check AI agent context includes timezone

### Developer Questions

- See utility function documentation above
- Check test files for examples
- Review this document for conventions

## Future Enhancements

Potential improvements:

- [ ] Per-workspace default timezone
- [ ] Meeting scheduler with availability across timezones
- [ ] Timezone indicators in UI (🌍 icon showing user's TZ)
- [ ] Admin dashboard showing user timezone distribution
- [ ] Automatic timezone detection on every login (optional)
