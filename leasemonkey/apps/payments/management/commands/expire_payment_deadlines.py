from django.core.management.base import BaseCommand
from apps.payments.views import expire_overdue_payment_deadlines


class Command(BaseCommand):
    help = (
        'Checks land registration requests with status=payment_pending and a missed '
        'admin-set payment_deadline, then rejects them automatically. '
        'Run daily via Task Scheduler or cron: '
        '  python manage.py expire_payment_deadlines'
    )

    def handle(self, *args, **options):
        count = expire_overdue_payment_deadlines()
        if count == 0:
            self.stdout.write('No overdue payment deadlines found.')
            return
        self.stdout.write(self.style.SUCCESS(f'✅ Expired {count} overdue payment deadline(s).'))