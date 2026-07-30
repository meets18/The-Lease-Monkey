from django.core.management.base import BaseCommand
from apps.payments.views import check_and_send_expiry_notifications


class Command(BaseCommand):
    help = (
        'Checks active land subscriptions and sends renewal reminder notifications '
        'to landowners whose subscriptions expire within 5 days. '
        'Run this daily via Task Scheduler or cron: '
        '  python manage.py send_expiry_notifications'
    )

    def handle(self, *args, **options):
        self.stdout.write('Checking subscriptions for upcoming expiry...')
        try:
            check_and_send_expiry_notifications()
            self.stdout.write(self.style.SUCCESS('✅ Expiry notifications sent successfully.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'❌ Error: {e}'))
