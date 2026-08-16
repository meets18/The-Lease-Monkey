from django.core.management.base import BaseCommand
from apps.accounts.views import purge_expired_deleted_users

class Command(BaseCommand):
    help = 'Permanently purges soft-deleted user accounts older than 24 hours.'

    def handle(self, *args, **options):
        count = purge_expired_deleted_users()
        self.stdout.write(self.style.SUCCESS(f'Successfully purged {count} soft-deleted user account(s) older than 24 hours.'))
