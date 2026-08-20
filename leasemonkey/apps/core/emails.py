"""Professional HTML email helpers for Lease Monkey.

Every transactional email in the app flows through send_templated_email()
so the sender name is consistently "TheLeaseMonkey" and each message uses
the matching HTML template in templates/emails/.

The actual delivery delegates to django.core.mail.send_mail (with an HTML
alternative) so call sites and tests that patch send_mail keep working.
"""
import re
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from email.utils import formataddr

APP_NAME = 'TheLeaseMonkey'


def _sender():
    """Branded sender: TheLeaseMonkey <the1leasemonkey@gmail.com>."""
    return formataddr((APP_NAME, settings.EMAIL_HOST_USER))


def _plain_text_fallback(html):
    """Crude-but-effective plain-text fallback derived from the HTML body."""
    text = strip_tags(html)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()


def send_templated_email(subject, to, template, context=None, fail_silently=True):
    """Send a branded HTML email rendered from templates/emails/<template>.

    Falls back to django.core.mail.send_mail so that any caller or test
    patching that function continues to intercept email delivery.
    """
    from django.core.mail import send_mail

    if isinstance(to, str):
        to = [to]
    context = dict(context or {})
    context.setdefault('app_name', APP_NAME)

    html = render_to_string(f'emails/{template}', context)
    plain = _plain_text_fallback(html)

    return send_mail(
        subject=subject,
        message=plain,
        from_email=_sender(),
        recipient_list=to,
        html_message=html,
        fail_silently=fail_silently,
    )


def send_templated_email_with_attachment(subject, to, template, context=None, attachment_path=None, fail_silently=True):
    """Like send_templated_email but attaches a file to the admin copy.

    The admin notification for new support tickets carries the user's
    attachment, so it uses EmailMultiAlternatives + attach_file.
    """
    from django.core.mail import EmailMultiAlternatives

    if isinstance(to, str):
        to = [to]
    context = dict(context or {})
    context.setdefault('app_name', APP_NAME)

    html = render_to_string(f'emails/{template}', context)
    plain = _plain_text_fallback(html)

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain,
        from_email=_sender(),
        to=to,
    )
    email.attach_alternative(html, 'text/html')
    if attachment_path:
        email.attach_file(attachment_path)
    return email.send(fail_silently=fail_silently)