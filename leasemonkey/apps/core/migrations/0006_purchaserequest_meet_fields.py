from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_notification_is_resolved_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='meet_link',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='meeting_datetime',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='meeting_duration_mins',
            field=models.PositiveIntegerField(default=30),
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='calendar_event_id',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
