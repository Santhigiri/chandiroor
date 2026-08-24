from datetime import datetime

def get_nazhika(current_time):
    """Calculate the current Nazhika from the time of day."""
    tzinfo = current_time.tzinfo
    sunrise = datetime(
        current_time.year,
        current_time.month,
        current_time.day,
        6, 0, 0,
        tzinfo=tzinfo
    )  # Approximate sunrise
    time_since_sunrise = current_time - sunrise
    nazhika = time_since_sunrise.total_seconds() / (24 * 60)
    return min(nazhika, 60)  # Ensure it's within 0-60
