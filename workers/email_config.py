"""
Email configuration for SendGrid and SMTP services

Supports multiple email services:
1. SendGrid - API-based (preferred)
2. SMTP - Gmail, Outlook, Yahoo, or any SMTP server

Priority: SendGrid > SMTP
"""
import os

# ===== SendGrid Configuration =====
# SendGrid API Key - Set via environment variable or .env file
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY', '')

# ===== SMTP Configuration (Gmail, Outlook, Yahoo, etc.) =====
# Works with any SMTP service:
# - Gmail: smtp.gmail.com:587 (requires App Password)
# - Outlook/Hotmail: smtp-mail.outlook.com:587 or smtp.office365.com:587
# - Yahoo: smtp.mail.yahoo.com:587 (requires App Password)
# - Custom SMTP: your.smtp.server:587

SMTP_HOST = os.getenv('SMTP_HOST', '')  # e.g., smtp.gmail.com or smtp-mail.outlook.com
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')  # Your email address
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')  # Password or App Password
SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'

# Legacy Gmail-specific settings (for backward compatibility)
GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')

# Auto-migrate Gmail settings to generic SMTP if set
if GMAIL_ADDRESS and GMAIL_APP_PASSWORD and not SMTP_HOST:
    SMTP_HOST = 'smtp.gmail.com'
    SMTP_USERNAME = GMAIL_ADDRESS
    SMTP_PASSWORD = GMAIL_APP_PASSWORD

# ===== Common Email Settings =====
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USERNAME or 'noreply@example.com')
FROM_NAME = os.getenv('FROM_NAME', 'Rightmove Property Scraper')

# Notification recipients (comma-separated)
NOTIFICATION_EMAILS = os.getenv('NOTIFICATION_EMAILS', '').split(',') if os.getenv('NOTIFICATION_EMAILS') else []

# Email templates
TEMPLATES = {
    'new_snapshots': {
        'subject': 'New Property Snapshots - {count} properties added',
    },
    'price_alert': {
        'subject': 'Price Change Alert - Property {property_id}',
    },
    'daily_digest': {
        'subject': 'Daily Property Digest - {date}',
    }
}

# ===== Auto-detect Email Service =====
def get_email_service():
    """
    Automatically detect which email service to use

    Returns:
        str: 'sendgrid', 'smtp', or 'none'
    """
    if SENDGRID_API_KEY:
        return 'sendgrid'
    elif SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD:
        return 'smtp'
    else:
        return 'none'

EMAIL_SERVICE = get_email_service()
