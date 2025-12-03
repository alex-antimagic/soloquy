# Outlook Integration Setup Guide

## Overview

The Outlook integration uses a **single Azure AD app registration per tenant**. This means:

- ✅ Admins create ONE Azure AD app for the entire workspace
- ✅ All users authenticate through the same app
- ✅ Each user gets their own access token scoped to their personal mailbox
- ✅ Microsoft automatically isolates access - users can only see their own emails

## For Administrators: One-Time Azure AD Setup

### Step 1: Create Azure AD App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations** → **New registration**
3. Configure:
   - **Name**: `YourCompany - Soloquy`
   - **Supported account types**: `Accounts in this organizational directory only`
   - Click **Register**

### Step 2: Configure Authentication

1. In your app, go to **Authentication**
2. Click **Add a platform** → **Web**
3. Add the redirect URI:
   ```
   https://your-domain.com/integrations/outlook/callback
   ```
4. Under **Implicit grant and hybrid flows**, enable:
   - ✅ Access tokens
   - ✅ ID tokens
5. Click **Save**

### Step 3: Create Client Secret

1. Go to **Certificates & secrets** → **Client secrets**
2. Click **New client secret**
3. Set:
   - **Description**: `Soloquy`
   - **Expires**: 24 months (recommended)
4. **Important**: Copy the secret **Value** immediately (you can't see it again)

### Step 4: Configure API Permissions

1. Go to **API permissions** → **Add a permission**
2. Select **Microsoft Graph** → **Delegated permissions**
3. Add these permissions:
   - `Mail.ReadWrite` - Read and write user mail
   - `Mail.Send` - Send mail as user
   - `Calendars.ReadWrite` - Read and write user calendars
   - `offline_access` - Maintain access to data
4. Click **Add permissions**

### Step 5: (Optional) Grant Admin Consent

To pre-approve for all users in your organization:
1. Click **Grant admin consent for [Your Organization]**
2. Confirm the consent

This prevents users from seeing the consent screen when they connect their personal Outlook.

### Step 6: Configure in Soloquy

1. In Soloquy, go to **Integrations** → **Outlook**
2. Click **Configure Workspace Outlook**
3. Enter:
   - **Application (client) ID**: From Azure app overview page
   - **Client Secret**: The value you copied in Step 3
4. Click **Save Credentials**
5. Complete the OAuth flow to connect a shared mailbox (optional)

## For Users: Connecting Personal Outlook

Once the admin has completed the Azure AD setup, users can connect their personal Outlook:

1. Go to **Integrations** → **Personal Integrations** section
2. Find **Outlook** and click **"Connect"**
3. Automatically redirected to Microsoft sign-in
4. Authenticate with your Microsoft credentials
5. Grant permissions (if admin consent wasn't given)
6. Redirected back to Soloquy - Done!

**That's it!** No configuration page, no credential entry. The system automatically:
- Uses the workspace Azure AD app credentials
- Creates your personal integration record
- Redirects you to Microsoft OAuth
- Stores your personal access token (scoped only to your mailbox)

## Architecture & Security

### How It Works

```
┌─────────────────────────────────────────┐
│   Azure AD App (One Per Tenant)        │
│   Client ID: abc-123                    │
│   Client Secret: xyz-789                │
└─────────────────────────────────────────┘
                   │
                   │ Used by all users
                   ▼
┌──────────────────────────────────────────────────────┐
│  User A authenticates                                │
│  → Gets Token A (scoped to User A's mailbox)        │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│  User B authenticates                                │
│  → Gets Token B (scoped to User B's mailbox)        │
└──────────────────────────────────────────────────────┘
```

### Security Features

1. **Delegated Permissions**: Each user grants access to their own mailbox
2. **Token Isolation**: Token A cannot access User B's emails (enforced by Microsoft)
3. **Automatic Refresh**: Tokens are refreshed automatically before expiry
4. **Encrypted Storage**: Client secrets and tokens are encrypted at rest
5. **OAuth 2.0**: Industry-standard authentication protocol

### Shared Mailboxes

Users can access shared mailboxes they have permissions for in Microsoft 365:

- The user's personal token is used
- Microsoft validates the user has access to the shared mailbox
- No separate authentication needed

Example: If User A has access to `support@company.com` in M365, their AI agents can read/send from that mailbox using the Graph API `users/support@company.com` endpoint.

## Troubleshooting

### "Azure AD credentials not configured"

**Problem**: User tries to connect personal Outlook but sees this error.

**Solution**: An admin must configure the workspace Outlook integration first.

### "Token refresh failed"

**Problem**: Access token expired and refresh token is invalid.

**Solution**:
1. User needs to disconnect and reconnect their Outlook
2. Check if Azure AD app secret has expired (renew in Azure Portal)

### "Access denied" when accessing shared mailbox

**Problem**: Agent can't read emails from shared mailbox.

**Solution**:
1. Verify the user has permissions to the shared mailbox in M365
2. Ensure the mailbox is configured as a "shared mailbox" (not a separate user account)

### Users see consent screen even after admin consent

**Possible causes**:
1. Admin consent was granted for wrong tenant
2. Azure app has "Accounts in any organizational directory" instead of "Accounts in this organizational directory only"
3. Permissions were added after admin consent (re-grant consent)

## Migration from Per-User App Registrations

If you previously had users create separate Azure AD apps, you can migrate:

1. Admin: Create a single workspace Azure AD app (follow steps above)
2. Admin: Configure the workspace integration in Soloquy
3. Each user: Disconnect their old personal integration
4. Each user: Reconnect using the new flow (will use workspace credentials automatically)
5. Users can delete their old Azure AD app registrations

## API Reference

The integration uses Microsoft Graph API with these endpoints:

- `GET /me/messages` - List emails
- `GET /me/messages/{id}` - Read specific email
- `POST /me/sendMail` - Send email
- `GET /me/calendar/events` - List calendar events
- `POST /me/calendar/events` - Create calendar event
- `GET /users/{shared-mailbox}/messages` - Access shared mailbox

Full API docs: https://learn.microsoft.com/en-us/graph/api/overview
