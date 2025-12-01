"""
Microsoft Outlook service using Graph API
Direct API calls without MCP complexity
"""
import requests
from typing import Dict, List, Any, Optional
from flask import current_app
from datetime import datetime, timedelta


class OutlookGraphService:
    """Service for Microsoft Outlook using Graph API directly"""

    BASE_URL = "https://graph.microsoft.com/v1.0"
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    def __init__(self, access_token: str, integration=None):
        """
        Initialize Outlook service with access token

        Args:
            access_token: OAuth access token for Microsoft Graph
            integration: Optional Integration model instance for token refresh
        """
        self.access_token = access_token
        self.integration = integration
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

    @staticmethod
    def refresh_access_token(integration):
        """
        Refresh Outlook access token using refresh token

        Args:
            integration: Integration model instance with OAuth credentials and refresh token

        Returns:
            dict: Dictionary with new access_token, refresh_token, and expires_in

        Raises:
            ValueError: If credentials or refresh token missing
            Exception: If token refresh fails
        """
        from app import db

        if not integration or not integration.client_id or not integration.client_secret:
            raise ValueError("Outlook OAuth credentials not configured")

        if not integration.refresh_token:
            raise ValueError("No refresh token available - user must re-authenticate")

        try:
            data = {
                'client_id': integration.client_id,
                'client_secret': integration.client_secret,
                'refresh_token': integration.refresh_token,
                'grant_type': 'refresh_token',
                'scope': ' '.join([
                    'https://graph.microsoft.com/Mail.ReadWrite',
                    'https://graph.microsoft.com/Mail.Send',
                    'https://graph.microsoft.com/Calendars.ReadWrite',
                    'offline_access'
                ])
            }

            response = requests.post(OutlookGraphService.TOKEN_URL, data=data)
            response.raise_for_status()

            result = response.json()

            # Update integration with new tokens
            integration.update_tokens(
                access_token=result['access_token'],
                refresh_token=result.get('refresh_token', integration.refresh_token),
                expires_in=result.get('expires_in', 3600)
            )
            db.session.commit()

            current_app.logger.info(f"Successfully refreshed Outlook token for integration {integration.id}")

            return {
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token', integration.refresh_token),
                'expires_in': result.get('expires_in', 3600)
            }

        except requests.exceptions.HTTPError as e:
            error_msg = f"Failed to refresh Outlook token: {e}"
            current_app.logger.error(error_msg)

            # If refresh fails, mark integration as inactive
            integration.is_active = False
            db.session.commit()

            raise Exception(error_msg)

    def _make_request_with_retry(self, method: str, url: str, **kwargs):
        """
        Make HTTP request with automatic token refresh on 401

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full URL for the request
            **kwargs: Additional arguments for requests (params, json, headers, etc.)

        Returns:
            Response object

        Raises:
            Exception: If request fails after retry
        """
        # Add headers if not provided
        if 'headers' not in kwargs:
            kwargs['headers'] = self.headers

        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and self.integration:
                # Token expired - try to refresh
                current_app.logger.info(f"Received 401, attempting token refresh for integration {self.integration.id}")

                try:
                    # Refresh token
                    result = self.refresh_access_token(self.integration)

                    # Update our headers with new token
                    self.access_token = result['access_token']
                    self.headers['Authorization'] = f'Bearer {self.access_token}'
                    kwargs['headers'] = self.headers

                    # Retry request with new token
                    response = requests.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response

                except Exception as refresh_error:
                    current_app.logger.error(f"Token refresh failed: {refresh_error}")
                    raise Exception(f"Authentication failed and token refresh unsuccessful: {str(refresh_error)}")
            else:
                # Not a 401 or no integration for refresh - raise original error
                raise

    def list_emails(self, max_results: int = 10, folder: str = 'inbox') -> List[Dict]:
        """
        List emails from specified folder

        Args:
            max_results: Maximum number of emails to return
            folder: Folder name (inbox, sent, drafts, etc.)

        Returns:
            List of email dictionaries
        """
        try:
            url = f"{self.BASE_URL}/me/mailFolders/{folder}/messages"
            params = {
                '$top': max_results,
                '$select': 'id,subject,from,receivedDateTime,bodyPreview,isRead',
                '$orderby': 'receivedDateTime DESC'
            }

            response = self._make_request_with_retry('GET', url, params=params)
            data = response.json()
            emails = data.get('value', [])

            # Format emails for Claude
            formatted_emails = []
            for email in emails:
                formatted_emails.append({
                    'id': email.get('id'),
                    'subject': email.get('subject'),
                    'from': email.get('from', {}).get('emailAddress', {}).get('address'),
                    'from_name': email.get('from', {}).get('emailAddress', {}).get('name'),
                    'received': email.get('receivedDateTime'),
                    'preview': email.get('bodyPreview'),
                    'is_read': email.get('isRead', False)
                })

            return formatted_emails

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error listing Outlook emails: {e}")
            raise Exception(f"Failed to list emails: {str(e)}")

    def read_email(self, email_id: str) -> Dict:
        """
        Read full content of specific email

        Args:
            email_id: Email message ID

        Returns:
            Email details dictionary
        """
        try:
            url = f"{self.BASE_URL}/me/messages/{email_id}"
            params = {
                '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview,isRead,hasAttachments'
            }

            response = self._make_request_with_retry('GET', url, params=params)
            email = response.json()

            # Format for Claude
            return {
                'id': email.get('id'),
                'subject': email.get('subject'),
                'from': email.get('from', {}).get('emailAddress', {}).get('address'),
                'from_name': email.get('from', {}).get('emailAddress', {}).get('name'),
                'to': [r.get('emailAddress', {}).get('address') for r in email.get('toRecipients', [])],
                'cc': [r.get('emailAddress', {}).get('address') for r in email.get('ccRecipients', [])],
                'received': email.get('receivedDateTime'),
                'body': email.get('body', {}).get('content'),
                'body_type': email.get('body', {}).get('contentType'),
                'preview': email.get('bodyPreview'),
                'is_read': email.get('isRead', False),
                'has_attachments': email.get('hasAttachments', False)
            }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error reading Outlook email {email_id}: {e}")
            raise Exception(f"Failed to read email: {str(e)}")

    def search_emails(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search emails by query

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            List of matching email dictionaries
        """
        try:
            url = f"{self.BASE_URL}/me/messages"
            params = {
                '$search': f'"{query}"',
                '$top': max_results,
                '$select': 'id,subject,from,receivedDateTime,bodyPreview,isRead',
                '$orderby': 'receivedDateTime DESC'
            }

            response = self._make_request_with_retry('GET', url, params=params)
            data = response.json()
            emails = data.get('value', [])

            # Format emails for Claude
            formatted_emails = []
            for email in emails:
                formatted_emails.append({
                    'id': email.get('id'),
                    'subject': email.get('subject'),
                    'from': email.get('from', {}).get('emailAddress', {}).get('address'),
                    'from_name': email.get('from', {}).get('emailAddress', {}).get('name'),
                    'received': email.get('receivedDateTime'),
                    'preview': email.get('bodyPreview'),
                    'is_read': email.get('isRead', False)
                })

            return formatted_emails

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error searching Outlook emails: {e}")
            raise Exception(f"Failed to search emails: {str(e)}")

    def send_email(self, to: List[str], subject: str, body: str,
                   body_type: str = 'Text', cc: Optional[List[str]] = None) -> Dict:
        """
        Send an email

        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body content
            body_type: 'Text' or 'HTML'
            cc: Optional list of CC recipients

        Returns:
            Success status dictionary
        """
        try:
            url = f"{self.BASE_URL}/me/sendMail"

            message = {
                'message': {
                    'subject': subject,
                    'body': {
                        'contentType': body_type,
                        'content': body
                    },
                    'toRecipients': [
                        {'emailAddress': {'address': addr}} for addr in to
                    ]
                }
            }

            if cc:
                message['message']['ccRecipients'] = [
                    {'emailAddress': {'address': addr}} for addr in cc
                ]

            response = self._make_request_with_retry('POST', url, json=message)
            return {'success': True, 'message': 'Email sent successfully'}

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error sending Outlook email: {e}")
            raise Exception(f"Failed to send email: {str(e)}")

    def list_calendar_events(self, max_results: int = 10, days_ahead: int = 7) -> List[Dict]:
        """
        List upcoming calendar events

        Args:
            max_results: Maximum number of events to return
            days_ahead: Number of days ahead to look for events

        Returns:
            List of calendar event dictionaries
        """
        try:
            # Calculate date range
            start_time = datetime.utcnow().isoformat() + 'Z'
            end_time = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'

            url = f"{self.BASE_URL}/me/calendarview"
            params = {
                'startDateTime': start_time,
                'endDateTime': end_time,
                '$top': max_results,
                '$select': 'id,subject,start,end,location,attendees,organizer,isOnlineMeeting,onlineMeetingUrl,bodyPreview',
                '$orderby': 'start/dateTime'
            }

            response = self._make_request_with_retry('GET', url, params=params)
            data = response.json()
            events = data.get('value', [])

            # Format events for Claude
            formatted_events = []
            for event in events:
                formatted_events.append({
                    'id': event.get('id'),
                    'subject': event.get('subject'),
                    'start': event.get('start', {}).get('dateTime'),
                    'end': event.get('end', {}).get('dateTime'),
                    'timezone': event.get('start', {}).get('timeZone'),
                    'location': event.get('location', {}).get('displayName'),
                    'organizer': event.get('organizer', {}).get('emailAddress', {}).get('address'),
                    'attendees': [
                        {
                            'email': a.get('emailAddress', {}).get('address'),
                            'name': a.get('emailAddress', {}).get('name'),
                            'response': a.get('status', {}).get('response')
                        }
                        for a in event.get('attendees', [])
                    ],
                    'is_online_meeting': event.get('isOnlineMeeting', False),
                    'meeting_url': event.get('onlineMeetingUrl'),
                    'preview': event.get('bodyPreview')
                })

            return formatted_events

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error listing calendar events: {e}")
            raise Exception(f"Failed to list calendar events: {str(e)}")

    def create_calendar_event(self, subject: str, start: str, end: str,
                              attendees: Optional[List[str]] = None,
                              location: Optional[str] = None,
                              body: Optional[str] = None,
                              is_online_meeting: bool = False) -> Dict:
        """
        Create a calendar event

        Args:
            subject: Event title
            start: Start time in ISO format (e.g., "2024-01-15T14:00:00")
            end: End time in ISO format
            attendees: Optional list of attendee email addresses
            location: Optional location string
            body: Optional event description
            is_online_meeting: Whether to create Teams meeting

        Returns:
            Created event dictionary
        """
        try:
            url = f"{self.BASE_URL}/me/events"

            event_data = {
                'subject': subject,
                'start': {
                    'dateTime': start,
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': end,
                    'timeZone': 'UTC'
                },
                'isOnlineMeeting': is_online_meeting
            }

            if attendees:
                event_data['attendees'] = [
                    {
                        'emailAddress': {'address': email},
                        'type': 'required'
                    }
                    for email in attendees
                ]

            if location:
                event_data['location'] = {'displayName': location}

            if body:
                event_data['body'] = {
                    'contentType': 'Text',
                    'content': body
                }

            response = self._make_request_with_retry('POST', url, json=event_data)
            created_event = response.json()

            return {
                'success': True,
                'event_id': created_event.get('id'),
                'subject': created_event.get('subject'),
                'start': created_event.get('start', {}).get('dateTime'),
                'end': created_event.get('end', {}).get('dateTime'),
                'meeting_url': created_event.get('onlineMeetingUrl') if is_online_meeting else None
            }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error creating calendar event: {e}")
            raise Exception(f"Failed to create calendar event: {str(e)}")

    def get_free_busy(self, emails: List[str], start: str, end: str) -> Dict:
        """
        Check free/busy status for attendees

        Args:
            emails: List of email addresses to check
            start: Start time in ISO format
            end: End time in ISO format

        Returns:
            Free/busy information dictionary
        """
        try:
            url = f"{self.BASE_URL}/me/calendar/getSchedule"

            request_data = {
                'schedules': emails,
                'startTime': {
                    'dateTime': start,
                    'timeZone': 'UTC'
                },
                'endTime': {
                    'dateTime': end,
                    'timeZone': 'UTC'
                },
                'availabilityViewInterval': 60  # 60-minute intervals
            }

            response = self._make_request_with_retry('POST', url, json=request_data)
            data = response.json()
            schedules = data.get('value', [])

            # Format for Claude
            availability = {}
            for schedule in schedules:
                email = schedule.get('scheduleId')
                availability[email] = {
                    'availability': schedule.get('availabilityView'),
                    'schedule_items': [
                        {
                            'start': item.get('start', {}).get('dateTime'),
                            'end': item.get('end', {}).get('dateTime'),
                            'status': item.get('status')
                        }
                        for item in schedule.get('scheduleItems', [])
                    ]
                }

            return availability

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error getting free/busy: {e}")
            raise Exception(f"Failed to get free/busy information: {str(e)}")
