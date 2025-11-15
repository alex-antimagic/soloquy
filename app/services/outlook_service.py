"""
Microsoft Outlook service using Graph API
Direct API calls without MCP complexity
"""
import requests
from typing import Dict, List, Any, Optional
from flask import current_app


class OutlookGraphService:
    """Service for Microsoft Outlook using Graph API directly"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str):
        """
        Initialize Outlook service with access token

        Args:
            access_token: OAuth access token for Microsoft Graph
        """
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

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

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

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

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

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

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

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

            response = requests.post(url, headers=self.headers, json=message)
            response.raise_for_status()

            return {'success': True, 'message': 'Email sent successfully'}

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error sending Outlook email: {e}")
            raise Exception(f"Failed to send email: {str(e)}")
