from django.core.management.base import BaseCommand
from apps.payments.views import check_and_expire_subscriptions, check_and_send_expiry_notifications


class Command(BaseCommand):
    help = (
        'Checks active land subscriptions and expires those whose end date has passed, '
        'taking the land offline automatically and notifying the owner. Also sends 5-day expiry warnings. '
        'Run daily via Task Scheduler or cron: '
        '  python manage.py expire_subscriptions'
    )

    def handle(self, *args, **options):
        self.stdout.write('Checking subscriptions for expiration and renewal reminders...')
        try:
            check_and_expire_subscriptions()
            check_and_send_expiry_notifications()
            self.stdout.write(self.style.SUCCESS('[SUCCESS] Subscription expiry check completed successfully.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'[ERROR] Error: {e}'))
