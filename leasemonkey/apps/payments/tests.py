from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from apps.lands.models import Land, LandRegistrationRequest
from apps.payments.models import LandSubscription
from apps.payments.views import resolve_hosting_amount, expire_overdue_payment_deadlines

User = get_user_model()


class HostingAmountResolutionTests(TestCase):
    """The admin-set monthly fee must flow into payment orders (no GST)."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='payres_owner',
            email='payres_owner@test.com',
            password='Password123!',
            role='LAND_OWNER',
            is_verified=True
        )
        self.land = Land.objects.create(
            owner=self.owner,
            name='Amount Res Land',
            slug='amount-res-land',
            area=5.0,
            average_plot_price=2000000,
            is_live=False
        )

    def test_resolve_uses_request_amount_when_payment_pending(self):
        req = LandRegistrationRequest.objects.create(
            owner=self.owner,
            property_name='Amount Res Land',
            state='Rajasthan',
            district='Jaipur',
            city_village='Jaipur',
            pin_code='302001',
            location='26.9, 75.8',
            average_plot_price=2000000,
            status='payment_pending',
            land=self.land,
            payment_amount=300.00,
            payment_deadline=timezone.now() + timedelta(days=3)
        )
        amount, sub = resolve_hosting_amount(self.land)
        self.assertEqual(float(amount), 300.00)

    def test_resolve_reuses_subscription_amount_for_renewal(self):
        sub = LandSubscription.objects.create(
            land=self.land,
            user=self.owner,
            amount=150.00,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30)
        )
        amount, resolved_sub = resolve_hosting_amount(self.land)
        self.assertEqual(float(amount), 150.00)
        self.assertEqual(resolved_sub.pk, sub.pk)

    def test_resolve_falls_back_to_default(self):
        amount, sub = resolve_hosting_amount(self.land)
        self.assertEqual(float(amount), 200.00)


class ExpireOverduePaymentDeadlinesTests(TestCase):
    """Overdue admin-set deadlines auto-reject the registration request."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='exp_owner',
            email='exp_owner@test.com',
            password='Password123!',
            role='LAND_OWNER',
            is_verified=True
        )
        self.land = Land.objects.create(
            owner=self.owner,
            name='Expire Land',
            slug='expire-land',
            area=5.0,
            average_plot_price=2000000,
            is_live=False
        )

    def test_overdue_request_is_rejected(self):
        req = LandRegistrationRequest.objects.create(
            owner=self.owner,
            property_name='Expire Land',
            state='Rajasthan',
            district='Jaipur',
            city_village='Jaipur',
            pin_code='302001',
            location='26.9, 75.8',
            average_plot_price=2000000,
            status='payment_pending',
            land=self.land,
            payment_amount=250.00,
            payment_deadline=timezone.now() - timedelta(hours=1)
        )
        count = expire_overdue_payment_deadlines()
        self.assertEqual(count, 1)
        req.refresh_from_db()
        self.assertEqual(req.status, 'rejected')
        self.assertIn('₹250', req.rejection_reason)

    def test_future_deadline_not_expired(self):
        req = LandRegistrationRequest.objects.create(
            owner=self.owner,
            property_name='Expire Land',
            state='Rajasthan',
            district='Jaipur',
            city_village='Jaipur',
            pin_code='302001',
            location='26.9, 75.8',
            average_plot_price=2000000,
            status='payment_pending',
            land=self.land,
            payment_amount=250.00,
            payment_deadline=timezone.now() + timedelta(days=2)
        )
        count = expire_overdue_payment_deadlines()
        self.assertEqual(count, 0)
        req.refresh_from_db()
        self.assertEqual(req.status, 'payment_pending')