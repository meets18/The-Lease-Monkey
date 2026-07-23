from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import EmailOTP, PurchaseRequest
from apps.lands.models import Land, Plot
import json

User = get_user_model()

class PurchaseRequestFormTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.buyer = User.objects.create_user(
            username='pr_buyer',
            email='pr_buyer@test.com',
            password='Password123!',
            role='BUYER',
            phone_number='+919876543210',
            is_verified=True
        )
        self.owner = User.objects.create_user(
            username='pr_owner',
            email='pr_owner@test.com',
            password='Password123!',
            role='LAND_OWNER',
            is_verified=True
        )
        self.land = Land.objects.create(
            name="Test Land",
            owner=self.owner,
            slug="test-land",
            area=10.0,
            average_plot_price=1500000,
            is_live=True
        )
        self.plot = Plot.objects.create(
            land=self.land,
            plot_number="Plot101",
            price=1500000,
            status="available",
            area="1500 sqft",
            coordinates=[[26.9, 75.8], [26.91, 75.8], [26.91, 75.81], [26.9, 75.8]]
        )

    def test_submit_purchase_request_without_otp(self):
        self.client.login(username='pr_buyer', password='Password123!')
        payload = {
            'full_name': 'PR Buyer',
            'aadhaar_number': '123456789012',
            'pan_number': 'ABCDE1234F',
            'proposed_amount': 1500000
        }
        url = reverse('lands:submit_purchase_request', kwargs={'slug': 'test-land', 'plot_number': 'Plot101'})
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('OTP is required', response.json()['error'])

    def test_submit_purchase_request_success(self):
        self.client.login(username='pr_buyer', password='Password123!')
        
        # Pre-verify with EmailOTP
        EmailOTP.objects.create(email='pr_buyer@test.com', otp_code='123456', is_used=True)
        
        payload = {
            'full_name': 'PR Buyer',
            'aadhaar_number': '123456789012',
            'pan_number': 'ABCDE1234F',
            'proposed_amount': 1450000
        }
        url = reverse('lands:submit_purchase_request', kwargs={'slug': 'test-land', 'plot_number': 'Plot101'})
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify created request attributes (should pull email/phone from logged in buyer user)
        pr = PurchaseRequest.objects.get(buyer=self.buyer, land=self.land, plot_number="Plot101")
        self.assertEqual(pr.email, 'pr_buyer@test.com')
        self.assertEqual(pr.phone_number, '+919876543210')
        self.assertEqual(pr.proposed_amount, 1450000)

    def test_fix_meeting_success(self):
        # Create a pending purchase request
        pr = PurchaseRequest.objects.create(
            buyer=self.buyer,
            land=self.land,
            plot_number="Plot101",
            full_name='PR Buyer',
            aadhaar_number='123456789012',
            pan_number='ABCDE1234F',
            email='pr_buyer@test.com',
            phone_number='+919876543210',
            proposed_amount=1450000,
            status='pending'
        )
        
        self.client.login(username='pr_owner', password='Password123!')
        url = reverse('lands:purchase_request_action', kwargs={'request_id': pr.id})
        
        payload = {
            'action': 'fix_meeting',
            'meeting_datetime': '2026-07-22T10:00',
            'duration_minutes': 45,
            'message': 'Let us discuss details.'
        }
        
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verify DB state
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'meeting_scheduled')
        self.assertEqual(pr.meeting_duration_mins, 45)
        
        # Verify plot status became reserved
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.status, 'reserved')
from apps.lands.models import LandRegistrationRequest
from django.core.exceptions import PermissionDenied

class SecurityAndChatTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.landowner = User.objects.create_user(
            username='landowner_test',
            email='landowner@test.com',
            password='Password123!',
            role='LAND_OWNER',
            is_verified=True
        )
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Password123!',
            role='ADMIN',
            is_superuser=True,
            is_verified=True
        )
        self.buyer = User.objects.create_user(
            username='buyer_test',
            email='buyer@test.com',
            password='Password123!',
            role='BUYER',
            is_verified=True
        )
        self.req = LandRegistrationRequest.objects.create(
            owner=self.landowner,
            property_name='Greenfields',
            state='Rajasthan',
            district='Jaipur',
            city_village='Jaipur',
            pin_code='302001',
            location='26.9, 75.8',
            average_plot_price=2000000,
            status='pending'
        )
        self.land = Land.objects.create(
            owner=self.landowner,
            name='Greenfields',
            slug='greenfields',
            area=5.0,
            average_plot_price=2000000,
            is_live=False
        )

    def test_resubmission_locking(self):
        self.client.login(username='landowner_test', password='Password123!')
        url = reverse('lands:landowner_request_data', kwargs={'req_id': self.req.id})
        
        # 1. Under pending review, it should be locked
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Only rejected requests', response.json()['error'])

        # 2. Under rejected, it should allow pre-fill
        self.req.status = 'rejected'
        self.req.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['property_name'], 'Greenfields')

    def test_digitization_gating(self):
        url = reverse('lands:plot_viewer', kwargs={'slug': 'greenfields'})
        
        # 1. Anonymous/unauthenticated user gets 403 PermissionDenied
        self.client.logout()
        try:
            response = self.client.get(url)
            # Django test client might return 403 or raise PermissionDenied
            self.assertEqual(response.status_code, 403)
        except PermissionDenied:
            pass

        # 2. Buyer user gets 403 PermissionDenied
        self.client.login(username='buyer_test', password='Password123!')
        try:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
        except PermissionDenied:
            pass

        # 3. Land owner gets 200 success
        self.client.login(username='landowner_test', password='Password123!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # 4. Admin gets 200 success
        self.client.login(username='admin_test', password='Password123!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

