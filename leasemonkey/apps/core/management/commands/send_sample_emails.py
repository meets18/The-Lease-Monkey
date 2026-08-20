"""Send one sample of every transactional email type to the test users.

Usage:
  python manage.py send_sample_emails
  python manage.py send_sample_emails --to you@example.com   # override recipients
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.core.emails import send_templated_email, send_templated_email_with_attachment


class Command(BaseCommand):
    help = "Send a sample of every email template to the test users so they can be reviewed."

    def add_arguments(self, parser):
        parser.add_argument('--to', action='append', default=[], help='Email address to send to (repeatable).')

    def handle(self, *args, **options):
        from apps.accounts.models import User

        recipients = options.get('to') or []
        if not recipients:
            users = list(User.objects.all())
            recipients = sorted({u.email for u in users if u.email})
        recipients = [r for r in recipients if r]
        if not recipients:
            self.stderr.write('No recipients found. Provide --to or create users first.')
            return

        self.stdout.write(f'Sending to: {", ".join(recipients)}')

        def send(template, subject, ctx):
            try:
                send_templated_email(subject=subject, to=recipients, template=template, context=ctx, fail_silently=False)
                self.stdout.write(f'  OK  {template}')
            except Exception as e:
                self.stderr.write(f'FAIL {template}: {e}')

        # OTP / verification
        send('otp_email.html', '[Sample] Verify Your Email Address', {
            'otp': '483920', 'purpose': 'verify your email address', 'user_name': 'Buyer',
        })
        send('otp_email.html', '[Sample] OTP for Password Change', {
            'otp': '731264', 'purpose': 'change your password', 'user_name': 'Buyer',
        })

        # Password
        send('password_email.html', '[Sample] Password Reset OTP', {
            'otp': '915738', 'action': 'reset your password', 'user_name': 'Owner',
        })

        # Land registration
        send('land_registration_email.html', '[Sample] New Land Registration Request', {
            'stage': 'submitted', 'property_name': 'Green Valley Enclave', 'location': 'Pune, Maharashtra 411001',
            'owner_name': 'Smeet Patel', 'email': 'smeet3590@gmail.com', 'phone': '9876543210',
            'aadhaar': '123456789012', 'pan': 'ABCDE1234F', 'review_url': 'https://leasemonkey.com/admin/requests/',
        })
        send('land_registration_email.html', '[Sample] Registration Submitted (Owner Acknowledgment)', {
            'stage': 'submitted_ack', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
        })
        send('land_registration_email.html', '[Sample] Landowner Registration Approved (Credentials)', {
            'stage': 'approved', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
            'username': 'owner123', 'password': 'Temp@12345',
            'login_url': 'https://leasemonkey.com/accounts/login/landowner/',
        })
        send('land_registration_email.html', '[Sample] Property Digitized & Approved (Offline)', {
            'stage': 'approved_offline', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
        })
        send('land_registration_email.html', '[Sample] Payment Required', {
            'stage': 'payment_required', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
            'payment_amount': '₹5,000', 'payment_deadline': '05 Sep 2026, 06:00 PM',
        })
        send('land_registration_email.html', '[Sample] Registration Rejected', {
            'stage': 'rejected', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
            'reason': 'The ownership proof document is not legible. Please upload a clearer scan.',
        })
        send('land_registration_email.html', '[Sample] Information Required', {
            'stage': 'info_required', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
            'admin_message': 'Please confirm the exact boundary measurements of the north side of the property.',
        })
        send('land_registration_email.html', '[Sample] Document Re-upload Requested', {
            'stage': 'reupload_requested', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
            'doc_label': 'Ownership Proof', 'note': 'The previous scan is blurred.',
        })
        send('land_registration_email.html', '[Sample] Re-upload Closed', {
            'stage': 'reupload_closed', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
        })
        send('land_registration_email.html', '[Sample] Document Re-uploaded (Admin)', {
            'stage': 'reupload_submitted', 'property_name': 'Green Valley Enclave',
            'doc_label': 'Ownership Proof', 'owner_name': 'Smeet',
        })
        send('land_registration_email.html', '[Sample] Property Live', {
            'stage': 'live', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
        })
        send('land_registration_email.html', '[Sample] Land Layout Deleted', {
            'stage': 'layout_deleted', 'property_name': 'Green Valley Enclave', 'user_name': 'Smeet',
        })

        # Purchase requests
        send('purchase_request_email.html', '[Sample] New Purchase Request', {
            'stage': 'new_request', 'user_name': 'Owner', 'buyer_name': 'Meet Shah',
            'plot_number': 'A-1', 'land_name': 'Green Valley Enclave', 'amount': '₹12,50,000',
            'phone': '9812345678', 'buyer_message': 'I would like to visit the site this weekend.',
        })
        send('purchase_request_email.html', '[Sample] Purchase Request Submitted', {
            'stage': 'submitted_ack', 'user_name': 'Meet', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
        })
        send('purchase_request_email.html', '[Sample] Meeting Scheduled', {
            'stage': 'meeting_scheduled', 'user_name': 'Meet', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
            'meeting_dt': '24 Aug 2026 at 11:30 AM IST', 'duration': 30, 'meet_link': 'https://meet.google.com/abc-defg-hij',
        })
        send('purchase_request_email.html', '[Sample] Purchase Request Approved', {
            'stage': 'approved', 'user_name': 'Meet', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
        })
        send('purchase_request_email.html', '[Sample] Purchase Request Rejected', {
            'stage': 'rejected', 'user_name': 'Meet', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
            'reason': 'The seller decided not to proceed with the sale.',
        })
        send('purchase_request_email.html', '[Sample] Purchase Request Cancelled', {
            'stage': 'cancelled', 'user_name': 'Owner', 'buyer_name': 'Meet Shah', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
        })
        send('purchase_request_email.html', '[Sample] Vacate Request', {
            'stage': 'vacate_request', 'user_name': 'Owner', 'buyer_name': 'Meet Shah', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
            'reason': 'Relocating to another city for work.',
        })
        send('purchase_request_email.html', '[Sample] Vacate Approved', {
            'stage': 'vacate_approved', 'user_name': 'Meet', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
        })
        send('purchase_request_email.html', '[Sample] Vacate Declined', {
            'stage': 'vacate_declined', 'user_name': 'Meet', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
        })
        send('purchase_request_email.html', '[Sample] De-allotment Notice', {
            'stage': 'deallotment_notice', 'user_name': 'Meet', 'buyer_name': 'Meet Shah', 'plot_number': 'A-1', 'land_name': 'Green Valley Enclave',
            'reason': 'Non-payment of agreed installments.',
        })
        send('purchase_request_email.html', '[Sample] Deletion Request (Admin)', {
            'stage': 'deletion_request', 'user_name': 'Admin', 'item_label': 'Plot A-1 in Green Valley Enclave',
            'land_name': 'Green Valley Enclave', 'requested_by': 'owner123',
        })
        send('purchase_request_email.html', '[Sample] Deletion Approved', {
            'stage': 'deletion_approved', 'user_name': 'Owner', 'item_label': 'Plot A-1 in Green Valley Enclave',
        })
        send('purchase_request_email.html', '[Sample] Deletion Rejected', {
            'stage': 'deletion_rejected', 'user_name': 'Owner', 'item_label': 'Plot A-1 in Green Valley Enclave',
            'reason': 'The plot has an active allotment.',
        })

        # Account deletion
        send('account_deletion_email.html', '[Sample] Buyer Account Deleted', {
            'stage': 'buyer_deleted', 'user_name': 'Buyer', 'reason': 'Requested by user.',
        })
        send('account_deletion_email.html', '[Sample] Landowner Account Deleted', {
            'stage': 'landowner_deleted', 'user_name': 'Owner', 'reason': 'Requested by user.',
        })

        # Support tickets
        send('support_email.html', '[Sample] New Support Ticket (Admin)', {
            'stage': 'ticket_admin', 'ticket_id': 'LM-2026-0042', 'user_name': 'meetsh', 'role': 'BUYER',
            'email': 'meetsh1818@gmail.com', 'subject': 'Unable to upload PAN document', 'category': 'Technical Issue',
            'description': 'The upload keeps failing with a timeout error on my laptop.',
        })
        send('support_email.html', '[Sample] Support Ticket Received', {
            'stage': 'ticket_ack', 'ticket_id': 'LM-2026-0042', 'user_name': 'Meet', 'subject': 'Unable to upload PAN document', 'category': 'Technical Issue',
        })
        send('support_email.html', '[Sample] Support Reply (User)', {
            'stage': 'ticket_reply_user', 'user_name': 'Meet', 'ticket_id': 'LM-2026-0042',
            'reply_message': 'We have fixed the upload issue. Please try again from the dashboard.',
        })
        send('support_email.html', '[Sample] Support Reply (Admin)', {
            'stage': 'ticket_reply_admin', 'user_name': 'meetsh', 'ticket_id': 'LM-2026-0042', 'subject': 'Unable to upload PAN document',
            'reply_message': 'The issue has been resolved on our end.',
        })
        send('support_email.html', '[Sample] Ticket Status Changed', {
            'stage': 'ticket_status', 'user_name': 'Meet', 'ticket_id': 'LM-2026-0042', 'status': 'Resolved',
            'status_message': 'Your ticket "Unable to upload PAN document" status changed from In Progress to Resolved.',
        })

        # Contact
        send('contact_email.html', '[Sample] Contact Form Submission', {
            'name': 'Meet Shah', 'email': 'meetsh1818@gmail.com', 'subject': 'Question about EMI options',
            'message': 'Do you support monthly payment plans for plots?',
        })

        self.stdout.write(self.style.SUCCESS('All sample emails sent.'))