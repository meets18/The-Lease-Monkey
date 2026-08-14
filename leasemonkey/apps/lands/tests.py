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
            'proposed_amount': 1450000,
            'otp_code': '123456'
        }
        url = reverse('lands:submit_purchase_request', kwargs={'slug': 'test-land', 'plot_number': 'Plot101'})
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify created request attributes (should pull email/phone from logged in buyer user)
        pr = PurchaseRequest.objects.get(buyer=self.buyer, land=self.land, plot_number="Plot101")
        self.assertEqual(pr.email, 'pr_buyer@test.com')
        self.assertEqual(pr.phone_number, '+919876543210')
        self.assertEqual(pr.proposed_amount, 1450000)

    def test_submit_purchase_request_with_wrong_otp(self):
        self.client.login(username='pr_buyer', password='Password123!')

        # A used OTP exists, but the buyer submits a non-matching code
        EmailOTP.objects.create(email='pr_buyer@test.com', otp_code='123456', is_used=True)

        payload = {
            'full_name': 'PR Buyer',
            'aadhaar_number': '123456789012',
            'pan_number': 'ABCDE1234F',
            'proposed_amount': 1450000,
            'otp_code': '999999'
        }
        url = reverse('lands:submit_purchase_request', kwargs={'slug': 'test-land', 'plot_number': 'Plot101'})
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('OTP', response.json()['error'])

    def test_cancel_purchase_request(self):
        self.client.login(username='pr_buyer', password='Password123!')

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
        url = reverse('lands:purchase_request_cancel', kwargs={'request_id': pr.id})
        response = self.client.post(url, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

        pr.refresh_from_db()
        self.assertEqual(pr.status, 'cancelled')

    def test_cancel_purchase_request_not_owner(self):
        other_buyer = User.objects.create_user(
            username='pr_other_buyer',
            email='pr_other@test.com',
            password='Password123!',
            role='BUYER',
            is_verified=True
        )
        pr = PurchaseRequest.objects.create(
            buyer=other_buyer,
            land=self.land,
            plot_number="Plot101",
            full_name='Other Buyer',
            aadhaar_number='123456789012',
            pan_number='ABCDE1234F',
            email='pr_other@test.com',
            phone_number='+919876543210',
            proposed_amount=1450000,
            status='pending'
        )
        self.client.login(username='pr_buyer', password='Password123!')
        url = reverse('lands:purchase_request_cancel', kwargs={'request_id': pr.id})
        response = self.client.post(url, content_type='application/json')
        # get_object_or_404 scoped to buyer hides other users' requests (404, not 403)
        self.assertEqual(response.status_code, 404)

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

    def test_reject_blocked_before_meeting_concludes(self):
        # meeting is scheduled for a FUTURE time -> reject must be blocked
        from datetime import timedelta
        future_meeting = timezone.now() + timedelta(hours=2)
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
            status='meeting_scheduled',
            meeting_datetime=future_meeting,
            meeting_duration_mins=30,
        )
        self.client.login(username='pr_owner', password='Password123!')
        url = reverse('lands:purchase_request_action', kwargs={'request_id': pr.id})
        payload = {'action': 'reject', 'reason': 'Changed my mind'}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'meeting_scheduled')

    def test_reject_allowed_after_meeting_concludes(self):
        # meeting ended (started in the past + duration elapsed) -> reject works
        from datetime import timedelta
        past_meeting = timezone.now() - timedelta(hours=2)
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
            status='meeting_scheduled',
            meeting_datetime=past_meeting,
            meeting_duration_mins=30,
        )
        self.client.login(username='pr_owner', password='Password123!')
        url = reverse('lands:purchase_request_action', kwargs={'request_id': pr.id})
        payload = {'action': 'reject', 'reason': 'Changed my mind'}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'rejected')

    def test_reject_without_reason_still_required(self):
        from datetime import timedelta
        past_meeting = timezone.now() - timedelta(hours=2)
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
            status='meeting_scheduled',
            meeting_datetime=past_meeting,
            meeting_duration_mins=30,
        )
        self.client.login(username='pr_owner', password='Password123!')
        url = reverse('lands:purchase_request_action', kwargs={'request_id': pr.id})
        payload = {'action': 'reject', 'reason': ''}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_pending_reject_still_allowed(self):
        # Pending status is NOT affected by the meeting gating
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
            status='pending',
        )
        self.client.login(username='pr_owner', password='Password123!')
        url = reverse('lands:purchase_request_action', kwargs={'request_id': pr.id})
        payload = {'action': 'reject', 'reason': 'No longer interested'}
        response = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'rejected')
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


class DocumentReuploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.landowner = User.objects.create_user(
            username='reupload_owner',
            email='reupload_owner@test.com',
            password='Password123!',
            role='LAND_OWNER',
            is_verified=True
        )
        self.admin = User.objects.create_user(
            username='reupload_admin',
            email='reupload_admin@test.com',
            password='Password123!',
            role='ADMIN',
            is_superuser=True,
            is_verified=True
        )
        self.buyer = User.objects.create_user(
            username='reupload_buyer',
            email='reupload_buyer@test.com',
            password='Password123!',
            role='BUYER',
            is_verified=True
        )
        self.req = LandRegistrationRequest.objects.create(
            owner=self.landowner,
            property_name='Reupload Estates',
            state='Rajasthan',
            district='Jaipur',
            city_village='Jaipur',
            pin_code='302001',
            location='26.9, 75.8',
            average_plot_price=2000000,
            status='pending'
        )
        self.reupload_url = reverse('lands:landowner_reupload_document', kwargs={'req_id': self.req.id})
        self.admin_reupload_url = reverse('lands:admin_request_reupload', kwargs={'req_id': self.req.id})
        self.admin_disable_url = reverse('lands:admin_disable_reupload', kwargs={'req_id': self.req.id})

    def _upload_file(self, name='registry.pdf', content=b'%PDF-1.4 reupload'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(name, content, content_type='application/pdf')

    def test_admin_requests_reupload(self):
        self.client.login(username='reupload_admin', password='Password123!')
        response = self.client.post(self.admin_reupload_url, {
            'reupload_document': 'registry_sale_deed',
            'reupload_note': 'Blurry scan, please re-upload.'
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertTrue(self.req.reupload_requested)
        self.assertEqual(self.req.reupload_document, 'registry_sale_deed')
        self.assertEqual(self.req.reupload_note, 'Blurry scan, please re-upload.')
        self.assertIsNone(self.req.reupload_submitted_at)

    def test_admin_cannot_request_reupload_for_live_request(self):
        self.req.status = 'live'
        self.req.save()
        self.client.login(username='reupload_admin', password='Password123!')
        response = self.client.post(self.admin_reupload_url, {
            'reupload_document': 'registry_sale_deed',
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertFalse(self.req.reupload_requested)

    def test_non_admin_cannot_request_reupload(self):
        self.client.login(username='reupload_owner', password='Password123!')
        try:
            response = self.client.post(self.admin_reupload_url, {
                'reupload_document': 'registry_sale_deed',
            })
            self.assertIn(response.status_code, (403, 404))
        except PermissionDenied:
            pass
        self.req.refresh_from_db()
        self.assertFalse(self.req.reupload_requested)

    def test_landowner_reuploads_document(self):
        self.req.reupload_requested = True
        self.req.reupload_document = 'registry_sale_deed'
        self.req.save()

        self.client.login(username='reupload_owner', password='Password123!')
        response = self.client.post(self.reupload_url, {
            'reupload_file': self._upload_file(),
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertTrue(self.req.registry_sale_deed)
        self.assertIn('land_requests/reupload_owner/registry_', self.req.registry_sale_deed.name)
        self.assertIsNotNone(self.req.reupload_submitted_at)

    def test_landowner_cannot_reupload_when_not_requested(self):
        self.client.login(username='reupload_owner', password='Password123!')
        response = self.client.post(self.reupload_url, {
            'reupload_file': self._upload_file(),
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertFalse(self.req.registry_sale_deed)

    def test_landowner_cannot_reupload_when_live(self):
        self.req.reupload_requested = True
        self.req.reupload_document = 'registry_sale_deed'
        self.req.status = 'live'
        self.req.save()

        self.client.login(username='reupload_owner', password='Password123!')
        response = self.client.post(self.reupload_url, {
            'reupload_file': self._upload_file(),
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertFalse(self.req.registry_sale_deed)

    def test_reupload_rejects_wrong_extension(self):
        self.req.reupload_requested = True
        self.req.reupload_document = 'registry_sale_deed'
        self.req.save()

        self.client.login(username='reupload_owner', password='Password123!')
        response = self.client.post(self.reupload_url, {
            'reupload_file': self._upload_file(name='registry.exe'),
        })
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertFalse(self.req.registry_sale_deed)

    def test_other_user_cannot_reupload(self):
        self.req.reupload_requested = True
        self.req.reupload_document = 'registry_sale_deed'
        self.req.save()

        self.client.login(username='reupload_buyer', password='Password123!')
        response = self.client.post(self.reupload_url, {
            'reupload_file': self._upload_file(),
        })
        self.assertEqual(response.status_code, 404)
        self.req.refresh_from_db()
        self.assertFalse(self.req.registry_sale_deed)

    def test_admin_disable_reupload(self):
        self.req.reupload_requested = True
        self.req.reupload_document = 'registry_sale_deed'
        self.req.reupload_submitted_at = timezone.now()
        self.req.save()

        self.client.login(username='reupload_admin', password='Password123!')
        response = self.client.post(self.admin_disable_url)
        self.assertEqual(response.status_code, 302)
        self.req.refresh_from_db()
        self.assertFalse(self.req.reupload_requested)
        self.assertEqual(self.req.reupload_document, '')
        self.assertIsNone(self.req.reupload_submitted_at)


