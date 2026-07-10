"""
google_calendar.py
──────────────────
Provides a reusable helper to build an authenticated Google Calendar API
service using a stored Refresh Token.

The refresh token is generated ONCE via the /google/authorize/ flow and
stored in settings.GOOGLE_REFRESH_TOKEN (loaded from .env).
"""
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    """
    Build and return an authenticated Google Calendar API service object.
    Uses the refresh token stored in settings to obtain a fresh access token.
    """
    creds = Credentials(
        token=None,
        refresh_token=settings.GOOGLE_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    # Refresh to get a valid access token
    creds.refresh(Request())
    service = build('calendar', 'v3', credentials=creds)
    return service


def create_meet_event(
    *,
    title: str,
    description: str,
    start_datetime: datetime,
    duration_minutes: int,
    attendee_emails: list[str],
) -> dict:
    """
    Create a Google Calendar event with a Google Meet conference link.

    Returns a dict with:
        meet_link       – the https://meet.google.com/... URL
        event_id        – the Calendar event ID (for future cancellation)
        html_link       – link to the Calendar event page
        start_iso       – ISO-formatted start time
        end_iso         – ISO-formatted end time
    """
    service = get_calendar_service()

    end_datetime = start_datetime + timedelta(minutes=duration_minutes)

    # Build attendee list - always include the LeaseMonkey calendar owner
    calendar_email = getattr(settings, 'GOOGLE_CALENDAR_EMAIL', settings.EMAIL_HOST_USER)
    all_attendees = list({calendar_email} | set(attendee_emails))
    attendees_payload = [{'email': e} for e in all_attendees]

    event_body = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'attendees': attendees_payload,
        'conferenceData': {
            'createRequest': {
                'requestId': str(uuid.uuid4()),
                'conferenceSolutionKey': {'type': 'hangoutsMeet'},
            }
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 60},
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }

    created_event = service.events().insert(
        calendarId='primary',
        body=event_body,
        conferenceDataVersion=1,
        sendUpdates='all',  # Sends invitation emails to all attendees
    ).execute()

    meet_link = (
        created_event
        .get('conferenceData', {})
        .get('entryPoints', [{}])[0]
        .get('uri', '')
    )

    return {
        'meet_link': meet_link,
        'event_id': created_event.get('id'),
        'html_link': created_event.get('htmlLink'),
        'start_iso': start_datetime.isoformat(),
        'end_iso': end_datetime.isoformat(),
    }
