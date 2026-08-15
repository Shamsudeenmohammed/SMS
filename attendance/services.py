# attendance/services.py

def get_term_for_date(session, date):
    """
    Map an attendance date to a term ("1st", "2nd", "3rd") for the given
    academic session by splitting the session's date range into 3 equal parts.
    Dates before the session start map to "1st", after the end to "3rd".
    Returns "" when no session/date is available.
    """
    if not session or not session.start_date or not session.end_date:
        return ""

    total_days = (session.end_date - session.start_date).days + 1
    if total_days <= 0:
        return ""

    offset = (date - session.start_date).days
    if offset < 0:
        return "1st"
    if offset >= total_days:
        return "3rd"

    third = total_days / 3
    if offset < third:
        return "1st"
    if offset < 2 * third:
        return "2nd"
    return "3rd"
