from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.lands.models import LandRegistrationRequest


class Command(BaseCommand):
    help = (
        'Checks land registration requests with status=payment_pending and a missed '
        'payment_deadline (> 24h ago), then sets them back to rejected/expired. '
        'Run daily via Task Scheduler or cron: '
        '  python manage.py expire_payment_deadlines'
    )

    def handle(self, *args, **options):
        now = timezone.now()
        overdue = LandRegistrationRequest.objects.filter(
            status='payment_pending',
            payment_deadline__lt=now
        )
        count = overdue.count()
        if count == 0:
            self.stdout.write('No overdue payment deadlines found.')
            return

        for req in overdue:
            owner_name = req.owner.username
            self.stdout.write(f'  ❌ Expiring: {req.property_name} (owner: {owner_name}, deadline: {req.payment_deadline})')
            req.status = 'rejected'
            req.rejection_reason = (
                f'Payment deadline missed. The ₹200 hosting fee was not paid within '
                f'24 hours of approval (deadline: {req.payment_deadline.strftime("%d %b %Y, %I:%M %p")}). '
                f'Please resubmit your land registration request.'
            )
            req.save(update_fields=['status', 'rejection_reason'])

            # Notify landowner
            from apps.core.models import Notification
            Notification.objects.create(
                recipient=req.owner,
                notif_type='system',
                title='⚠️ Payment Deadline Missed — Registration Expired',
                message=(
                    f'Your land registration approval for "{req.property_name}" has expired '
                    f'because the ₹200 hosting fee was not paid within the 24-hour window. '
                    f'Please resubmit your registration request to start fresh.'
                )
            )

        self.stdout.write(self.style.SUCCESS(f'✅ Expired {count} overdue payment deadline(s).'))
