import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(['POST'])
@permission_classes([AllowAny])
def contact_us(request):
    """
    POST /contact_us/send/
    Body: { "email": "sender@example.com", "message": "Hello..." }

    Sends the message from the educonnectz Gmail account to educonnectz121@gmail.com.
    The Reply-To header is set to the user's email so you can reply directly to them.
    """
    email = request.data.get('email', '').strip()
    message = request.data.get('message', '').strip()

    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not message:
        return Response({'error': 'Message is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # ── Build the email ──────────────────────────────────────────
    smtp_host = settings.CONTACT_US_EMAIL_HOST
    smtp_port = settings.CONTACT_US_EMAIL_PORT
    smtp_use_tls = settings.CONTACT_US_EMAIL_USE_TLS
    smtp_user = settings.CONTACT_US_EMAIL_HOST_USER
    smtp_password = settings.CONTACT_US_EMAIL_HOST_PASSWORD
    from_name = settings.CONTACT_US_FROM_NAME
    from_email = settings.CONTACT_US_FROM_EMAIL
    recipient = settings.CONTACT_US_RECIPIENT_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'Contact Us – Message from {email}'
    msg['From'] = f'{from_name} <{from_email}>'
    msg['To'] = recipient
    msg['Reply-To'] = email

    plain_body = (
        f"You received a new contact request.\n\n"
        f"From: {email}\n\n"
        f"Message:\n{message}"
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #4A90E2;">New Contact Request</h2>
        <p><strong>From:</strong> {email}</p>
        <hr/>
        <p><strong>Message:</strong></p>
        <p style="background:#f5f5f5; padding:12px; border-radius:6px;">{message}</p>
        <hr/>
        <small style="color:#999;">Sent via EduConnectz Contact Form</small>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    # ── Send via SMTP ────────────────────────────────────────────
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [recipient], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        return Response(
            {'error': 'Email authentication failed. Check SMTP credentials.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except smtplib.SMTPException as exc:
        return Response(
            {'error': f'Failed to send email: {str(exc)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({'message': 'Your message has been sent successfully.'}, status=status.HTTP_200_OK)
