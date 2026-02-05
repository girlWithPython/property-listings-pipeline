
"""
Email worker tasks using SendGrid or Gmail SMTP

Supports multiple email services with automatic fallback:
1. SendGrid API (preferred)
2. Gmail SMTP (fallback)
"""
import asyncio
import asyncpg
import smtplib
from datetime import datetime, timedelta
from typing import List, Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

from workers.celery_app import app
from workers.email_config import (
    SENDGRID_API_KEY,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_USE_TLS,
    FROM_EMAIL,
    FROM_NAME,
    NOTIFICATION_EMAILS,
    TEMPLATES,
    EMAIL_SERVICE
)
from db.config import DB_CONFIG


def send_email_via_sendgrid(to_emails: List[str], subject: str, html_content: str) -> dict:
    """
    Send email using SendGrid API

    Args:
        to_emails: List of recipient email addresses
        subject: Email subject
        html_content: HTML email body

    Returns:
        dict with status and message
    """
    if not SENDGRID_AVAILABLE:
        print("[EMAIL ERROR] SendGrid library not installed")
        return {"status": "error", "message": "SendGrid not available"}

    if not SENDGRID_API_KEY:
        print("[EMAIL ERROR] SENDGRID_API_KEY not set")
        return {"status": "error", "message": "SendGrid API key not configured"}

    if not to_emails:
        print("[EMAIL ERROR] No recipient emails provided")
        return {"status": "error", "message": "No recipients"}

    try:
        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=[To(email) for email in to_emails],
            subject=subject,
            html_content=Content("text/html", html_content)
        )

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        print(f"[EMAIL-SENDGRID] Sent to {len(to_emails)} recipients: {subject}")
        print(f"[EMAIL-SENDGRID] Status code: {response.status_code}")

        return {
            "status": "success",
            "service": "sendgrid",
            "status_code": response.status_code,
            "recipients": len(to_emails)
        }

    except Exception as e:
        print(f"[EMAIL-SENDGRID ERROR] Failed to send email: {e}")
        return {"status": "error", "service": "sendgrid", "message": str(e)}


def send_email_via_smtp(to_emails: List[str], subject: str, html_content: str) -> dict:
    """
    Send email using SMTP (Gmail, Outlook, Yahoo, or any SMTP server)

    Args:
        to_emails: List of recipient email addresses
        subject: Email subject
        html_content: HTML email body

    Returns:
        dict with status and message
    """
    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        print("[EMAIL ERROR] SMTP credentials not configured")
        print("[EMAIL] Required: SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD")
        return {"status": "error", "message": "SMTP credentials not configured"}

    if not to_emails:
        print("[EMAIL ERROR] No recipient emails provided")
        return {"status": "error", "message": "No recipients"}

    # Detect SMTP provider for better logging
    smtp_provider = "SMTP"
    if "gmail" in SMTP_HOST.lower():
        smtp_provider = "GMAIL"
    elif "outlook" in SMTP_HOST.lower() or "office365" in SMTP_HOST.lower():
        smtp_provider = "OUTLOOK"
    elif "yahoo" in SMTP_HOST.lower():
        smtp_provider = "YAHOO"

    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{FROM_NAME} <{SMTP_USERNAME}>"
        msg['To'] = ', '.join(to_emails)

        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        # Connect to SMTP server
        print(f"[EMAIL-{smtp_provider}] Connecting to {SMTP_HOST}:{SMTP_PORT}")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)

        if SMTP_USE_TLS:
            server.starttls()

        # Login and send
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, to_emails, msg.as_string())
        server.quit()

        print(f"[EMAIL-{smtp_provider}] Sent to {len(to_emails)} recipients: {subject}")

        return {
            "status": "success",
            "service": "smtp",
            "provider": smtp_provider.lower(),
            "recipients": len(to_emails)
        }

    except smtplib.SMTPAuthenticationError as e:
        print(f"[EMAIL-{smtp_provider} ERROR] Authentication failed: {e}")
        if "gmail" in SMTP_HOST.lower():
            print(f"[EMAIL-{smtp_provider}] Gmail requires App Password (not regular password)")
            print(f"[EMAIL-{smtp_provider}] Generate at: https://myaccount.google.com/apppasswords")
        elif "outlook" in SMTP_HOST.lower() or "office365" in SMTP_HOST.lower():
            print(f"[EMAIL-{smtp_provider}] Try your regular Outlook/Hotmail password")
            print(f"[EMAIL-{smtp_provider}] Or use smtp.office365.com:587 if you have Office 365")
        return {"status": "error", "service": "smtp", "message": f"Authentication failed: {e}"}

    except Exception as e:
        print(f"[EMAIL-{smtp_provider} ERROR] Failed to send email: {e}")
        return {"status": "error", "service": "smtp", "message": str(e)}


def send_email_smart(to_emails: List[str], subject: str, html_content: str) -> dict:
    """
    Smart email sender - automatically chooses between SendGrid and SMTP

    Priority:
    1. SendGrid (if API key configured)
    2. SMTP (if credentials configured) - works with Gmail, Outlook, Yahoo, etc.
    3. Error (no service configured)

    Args:
        to_emails: List of recipient email addresses
        subject: Email subject
        html_content: HTML email body

    Returns:
        dict with status and message
    """
    if not to_emails:
        print("[EMAIL ERROR] No recipient emails provided")
        return {"status": "error", "message": "No recipients"}

    print(f"[EMAIL] Using service: {EMAIL_SERVICE}")

    if EMAIL_SERVICE == 'sendgrid':
        return send_email_via_sendgrid(to_emails, subject, html_content)
    elif EMAIL_SERVICE == 'smtp':
        return send_email_via_smtp(to_emails, subject, html_content)
    else:
        print("[EMAIL ERROR] No email service configured")
        print("[EMAIL] Configure either:")
        print("[EMAIL]   - SendGrid: Set SENDGRID_API_KEY")
        print("[EMAIL]   - SMTP: Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD")
        return {
            "status": "error",
            "message": "No email service configured (need SendGrid or SMTP credentials)"
        }


def format_property_html(property_data: dict) -> str:
    """
    Format a single property as HTML

    Args:
        property_data: Property dict from database

    Returns:
        HTML string
    """
    price_str = f"£{property_data['price']:,}" if property_data['price'] else "Price not available"
    bedrooms_str = f"{property_data['bedrooms']} bed" if property_data['bedrooms'] else "Bedrooms N/A"
    property_type = property_data.get('property_type') or 'Unknown type'
    offer_type = property_data.get('offer_type') or ''
    county = property_data.get('county') or ''
    postcode = property_data.get('postcode') or ''

    location = f"{postcode}, {county}" if postcode and county else (postcode or county or "Location N/A")

    return f"""
    <div style="border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px;">
        <h3 style="margin-top: 0;">
            <a href="{property_data['url']}" style="color: #0066cc; text-decoration: none;">
                {price_str} - {bedrooms_str} {property_type}
            </a>
        </h3>
        <p style="margin: 5px 0;">
            <strong>Property ID:</strong> {property_data['property_id']}<br>
            <strong>Type:</strong> {offer_type} {property_type}<br>
            <strong>Location:</strong> {location}<br>
            <strong>Snapshot Date:</strong> {property_data['created_at'].strftime('%Y-%m-%d %H:%M')}<br>
        </p>
        <p style="margin: 10px 0 0 0;">
            <a href="{property_data['url']}"
               style="background-color: #0066cc; color: white; padding: 8px 16px;
                      text-decoration: none; border-radius: 3px; display: inline-block;">
                View on Rightmove
            </a>
        </p>
    </div>
    """


@app.task(name='workers.email_tasks.send_email')
def send_email(to: str, subject: str, body: str):
    """
    Send a basic email.

    Args:
        to: Recipient email address (comma-separated for multiple)
        subject: Email subject
        body: Email body (HTML)
    """
    to_emails = [email.strip() for email in to.split(',')]
    return send_email_smart(to_emails, subject, body)


@app.task(name='workers.email_tasks.send_new_snapshots_notification')
def send_new_snapshots_notification(minutes: int = 60):
    """
    Send email notification about new property snapshots added in the last N minutes.

    Args:
        minutes: Look for snapshots added in the last N minutes (default: 60)
    """
    async def _get_new_snapshots():
        conn = await asyncpg.connect(**DB_CONFIG)

        try:
            # Get snapshots added in the last N minutes
            cutoff_time = datetime.now() - timedelta(minutes=minutes)

            properties = await conn.fetch("""
                SELECT
                    p.property_id,
                    p.url,
                    p.price,
                    p.bedrooms,
                    p.created_at,
                    pc.postcode,
                    c.name as county,
                    pt.name as property_type,
                    ot.name as offer_type
                FROM properties p
                LEFT JOIN postcodes pc ON p.postcode_id = pc.id
                LEFT JOIN counties c ON p.county_id = c.id
                LEFT JOIN property_types pt ON p.property_type_id = pt.id
                LEFT JOIN offer_types ot ON p.offer_type_id = ot.id
                WHERE p.created_at >= $1
                ORDER BY p.created_at DESC
            """, cutoff_time)

            return [dict(p) for p in properties]

        finally:
            await conn.close()

    # Get new snapshots
    try:
        new_snapshots = asyncio.run(_get_new_snapshots())
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            new_snapshots = asyncio.run(_get_new_snapshots())
        else:
            raise

    if not new_snapshots:
        print(f"[EMAIL] No new snapshots in the last {minutes} minutes")
        return {"status": "no_snapshots", "count": 0}

    if not NOTIFICATION_EMAILS:
        print(f"[EMAIL] No notification emails configured. Found {len(new_snapshots)} new snapshots.")
        return {"status": "no_recipients", "count": len(new_snapshots)}

    # Build email content
    subject = TEMPLATES['new_snapshots']['subject'].format(count=len(new_snapshots))

    properties_html = "".join([format_property_html(prop) for prop in new_snapshots])

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #0066cc; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .footer {{ background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>New Property Snapshots</h1>
            <p>{len(new_snapshots)} new properties added in the last {minutes} minutes</p>
        </div>
        <div class="content">
            <p>Here are the latest property snapshots from your Rightmove scraper:</p>
            {properties_html}
        </div>
        <div class="footer">
            <p>This is an automated notification from your Rightmove Property Scraper.</p>
            <p>Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """

    # Send email
    result = send_email_smart(NOTIFICATION_EMAILS, subject, html_content)
    result['snapshots_count'] = len(new_snapshots)

    return result


@app.task(name='workers.email_tasks.send_price_alert')
def send_price_alert(property_id: str, old_price: int, new_price: int):
    """
    Send price change alert email.

    Args:
        property_id: ID of the property
        old_price: Previous price
        new_price: New price
    """
    if not NOTIFICATION_EMAILS:
        print(f"[EMAIL] No notification emails configured")
        return {"status": "no_recipients"}

    async def _get_property_details():
        conn = await asyncpg.connect(**DB_CONFIG)
        try:
            prop = await conn.fetchrow("""
                SELECT
                    p.property_id,
                    p.url,
                    p.price,
                    p.bedrooms,
                    pc.postcode,
                    c.name as county,
                    pt.name as property_type
                FROM properties p
                LEFT JOIN postcodes pc ON p.postcode_id = pc.id
                LEFT JOIN counties c ON p.county_id = c.id
                LEFT JOIN property_types pt ON p.property_type_id = pt.id
                WHERE p.property_id = $1
                ORDER BY p.created_at DESC
                LIMIT 1
            """, property_id)
            return dict(prop) if prop else None
        finally:
            await conn.close()

    try:
        property_data = asyncio.run(_get_property_details())
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            property_data = asyncio.run(_get_property_details())
        else:
            raise

    if not property_data:
        print(f"[EMAIL] Property {property_id} not found")
        return {"status": "property_not_found"}

    price_change = new_price - old_price
    change_direction = "increased" if price_change > 0 else "decreased"
    change_color = "red" if price_change > 0 else "green"

    subject = TEMPLATES['price_alert']['subject'].format(property_id=property_id)

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #ff9900; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .price-change {{ font-size: 24px; font-weight: bold; color: {change_color}; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Price Change Alert</h1>
        </div>
        <div class="content">
            <h2>Property {property_id}</h2>
            <p class="price-change">
                Price {change_direction}: £{old_price:,} → £{new_price:,}
                ({price_change:+,})
            </p>
            <p>
                <strong>Location:</strong> {property_data.get('postcode', 'N/A')}, {property_data.get('county', 'N/A')}<br>
                <strong>Type:</strong> {property_data.get('bedrooms', 'N/A')} bed {property_data.get('property_type', 'N/A')}
            </p>
            <p>
                <a href="{property_data['url']}"
                   style="background-color: #0066cc; color: white; padding: 10px 20px;
                          text-decoration: none; border-radius: 3px; display: inline-block;">
                    View Property
                </a>
            </p>
        </div>
    </body>
    </html>
    """

    return send_email_smart(NOTIFICATION_EMAILS, subject, html_content)


@app.task(name='workers.email_tasks.send_daily_digest')
def send_daily_digest():
    """
    Send daily digest of new properties added in the last 24 hours.
    """
    return send_new_snapshots_notification(minutes=24 * 60)
