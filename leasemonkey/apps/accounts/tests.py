from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model, authenticate
from apps.accounts.models import UserPreferences
import json

User = get_user_model()


class UserPreferencesTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create landowner
        self.owner = User.objects.create_user(
            username='owner_test',
            email='owner@test.com',
            password='Password123',
            role=User.LAND_OWNER,
            phone_number='+919876543210'
        )
        # Create buyer
        self.buyer = User.objects.create_user(
            username='buyer_test',
            email='buyer@test.com',
            password='Password123',
            role=User.BUYER,
            phone_number='+919876543211'
        )

    def test_preferences_signal_auto_created(self):
        """Verify that UserPreferences model is created automatically via signal."""
        new_user = User.objects.create_user(
            username='new_user',
            email='new@test.com',
            password='Password123',
            phone_number='+919876543212'
        )
        self.assertTrue(UserPreferences.objects.filter(user=new_user).exists())

    def test_preferences_resilient_creation(self):
        """Verify view is resilient and recreates preferences if deleted."""
        # Delete preferences record
        UserPreferences.objects.filter(user=self.buyer).delete()
        self.assertFalse(UserPreferences.objects.filter(user=self.buyer).exists())

        # Log in and check profile page loads successfully
        self.client.login(username='buyer_test', password='Password123')
        response = self.client.get(reverse('profile') + '?section=preferences')
        self.assertEqual(response.status_code, 200)

        # Verify preferences record is auto-recreated
        self.assertTrue(UserPreferences.objects.filter(user=self.buyer).exists())

    def test_preferences_invalid_range_validations(self):
        """Verify validations prevent invalid range saves (negative values, min > max)."""
        self.client.login(username='buyer_test', password='Password123')

        # 1. Min budget > Max budget
        payload = {
            'min_budget': '5000',
            'max_budget': '1000',
            'min_acres': '1.5',
            'max_acres': '10',
            'property_condition': 'no_preference',
        }
        response = self.client.post(
            reverse('profile') + '?section=preferences',
            payload,
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('Minimum budget cannot exceed maximum budget.', data['errors']['min_budget'])

        # 2. Negative inputs
        payload_neg = {
            'min_budget': '-100',
            'max_budget': '1000',
            'min_acres': '-1.5',
            'max_acres': '10',
            'property_condition': 'no_preference',
        }
        response_neg = self.client.post(
            reverse('profile') + '?section=preferences',
            payload_neg,
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(response_neg.status_code, 400)
        data_neg = response_neg.json()
        self.assertIn('Minimum budget cannot be negative.', data_neg['errors']['min_budget'])
        self.assertIn('Minimum acres cannot be negative.', data_neg['errors']['min_acres'])

    def test_preferences_successful_save(self):
        """Verify that valid preferences inputs save correctly using JSON format lists."""
        self.client.login(username='buyer_test', password='Password123')

        payload = {
            'min_budget': '10000',
            'max_budget': '50000',
            'min_acres': '1.5',
            'max_acres': '5.5',
            'property_condition': 'never_leased',
            'proximity_preferences': ['school', 'highway']
        }
        response = self.client.post(
            reverse('profile') + '?section=preferences',
            payload,
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'done')

        # Retrieve and verify database record
        prefs = UserPreferences.objects.get(user=self.buyer)
        self.assertEqual(prefs.min_budget, 10000)
        self.assertEqual(prefs.max_budget, 50000)
        self.assertEqual(prefs.min_acres, 1.5)
        self.assertEqual(prefs.max_acres, 5.5)
        self.assertEqual(prefs.property_condition, 'never_leased')
        self.assertEqual(prefs.proximity_preferences, ['school', 'highway'])


class OnboardingFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_buyer_registration_validations(self):
        """Verify registration checks age, weak passwords, mismatch passwords and unique checks."""
        # 1. Underage check (User is under 18)
        payload = {
            'email': 'young@test.com',
            'first_name': 'Young User',
            'dob': '2015-05-10', # Age under 18
            'phone_country_code': '+91',
            'phone_number': '9876543299',
            'username': 'young123',
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        }
        response = self.client.post(reverse('buyer_register'), payload)
        self.assertEqual(response.status_code, 200) # Renders login template with errors
        # Unverified user should not be created
        self.assertFalse(User.objects.filter(username='young123').exists())

        # 2. Weak password check (Password needs to have 12 chars, upper, lower, digit, symbol)
        payload['dob'] = '2000-01-01' # Age 26
        payload['password'] = 'weak'
        payload['confirm_password'] = 'weak'
        response = self.client.post(reverse('buyer_register'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='young123').exists())

        # 3. Non-matching passwords check
        payload['password'] = 'StrongPassword123!'
        payload['confirm_password'] = 'DifferentPassword123!'
        response = self.client.post(reverse('buyer_register'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='young123').exists())

        # 4. Successful registration (creates unverified account)
        payload['password'] = 'StrongPassword123!'
        payload['confirm_password'] = 'StrongPassword123!'
        response = self.client.post(reverse('buyer_register'), payload)
        self.assertEqual(response.status_code, 302) # Redirects to verify_email view
        self.assertTrue(User.objects.filter(username='young123', is_verified=False).exists())

    def test_email_verification_flow(self):
        """Verify OTP verification activates user and initiates login session."""
        # Setup an unverified user
        unverified_user = User.objects.create_user(
            username='unverified123',
            email='unver@test.com',
            password='StrongPassword123!',
            first_name='Unverified',
            phone_number='+919876543000',
            role=User.BUYER,
            is_verified=False
        )
        
        # Create OTP
        from apps.core.models import EmailOTP
        EmailOTP.objects.create(email='unver@test.com', otp_code='123456')

        session = self.client.session
        session['verify_email_addr'] = 'unver@test.com'
        session.save()

        # Submit wrong OTP
        response = self.client.post(reverse('verify_email'), {'otp': '000000'})
        self.assertEqual(response.status_code, 200)
        unverified_user.refresh_from_db()
        self.assertFalse(unverified_user.is_verified)

        # Submit correct OTP
        response = self.client.post(reverse('verify_email'), {'otp': '123456'})
        self.assertEqual(response.status_code, 302) # Redirects to onboarding preferences
        unverified_user.refresh_from_db()
        self.assertTrue(unverified_user.is_verified)

    def test_onboarding_preferences_handling(self):
        """Verify preferences onboarding parses Indian number strings or defaults on skip."""
        buyer = User.objects.create_user(
            username='pref_buyer',
            email='pref@test.com',
            password='StrongPassword123!',
            role=User.BUYER,
            is_verified=True
        )
        self.client.login(username='pref_buyer', password='StrongPassword123!')

        # 1. Skip preferences (applies defaults: min=0, max=10 Lakhs)
        response = self.client.post(reverse('onboarding_preferences'), {'action': 'skip'})
        self.assertEqual(response.status_code, 302)
        prefs = UserPreferences.objects.get(user=buyer)
        self.assertEqual(prefs.min_budget, 0)
        self.assertEqual(prefs.max_budget, 1000000)

        # 2. Save preferences with Indian notation (e.g. 15L, 2,00,000)
        payload = {
            'action': 'save',
            'min_budget': '2L',
            'max_budget': '15,00,000',
            'min_acres': '1.0',
            'max_acres': '3.5',
            'property_condition': 'never_leased',
            'proximity_preferences': ['school']
        }
        response = self.client.post(reverse('onboarding_preferences'), payload)
        self.assertEqual(response.status_code, 302)
        prefs.refresh_from_db()
        self.assertEqual(prefs.min_budget, 200000)
        self.assertEqual(prefs.max_budget, 1500000)
        self.assertEqual(prefs.min_acres, 1.0)
        self.assertEqual(prefs.property_condition, 'never_leased')

    def test_forgot_password_flow(self):
        """Verify forgot password email verification and OTP password updates."""
        buyer = User.objects.create_user(
            username='recover_buyer',
            email='recover@test.com',
            password='OldPassword123!',
            role=User.BUYER,
            is_verified=True
        )

        # Request reset OTP
        response = self.client.post(reverse('forgot_password'), {'email': 'recover@test.com'})
        self.assertEqual(response.status_code, 302)

        # Get generated OTP
        from apps.core.models import EmailOTP
        record = EmailOTP.objects.filter(email='recover@test.com', is_used=False).first()
        self.assertIsNotNone(record)

        session = self.client.session
        session['reset_password_email'] = 'recover@test.com'
        session.save()

        # Submit OTP and new password
        payload = {
            'otp': record.otp_code,
            'new_password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!'
        }
        response = self.client.post(reverse('forgot_password_reset'), payload)
        self.assertEqual(response.status_code, 302)

        # Verify password updated successfully by trying to authenticate
        user = authenticate(username='recover_buyer', password='NewPassword123!')
        self.assertIsNotNone(user)


class AccountDeletionAndAdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.buyer = User.objects.create_user(
            username='delete_buyer',
            email='delete_buyer@test.com',
            password='Password123!',
            role='BUYER',
            is_verified=True
        )
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='AdminPassword123!',
            role='ADMIN',
            is_verified=True
        )

    def test_send_delete_otp(self):
        self.client.login(username='delete_buyer', password='Password123!')
        response = self.client.post(reverse('send_delete_otp'))
        self.assertEqual(response.status_code, 200)
        from apps.core.models import EmailOTP
        otp_record = EmailOTP.objects.filter(email='delete_buyer@test.com').first()
        self.assertIsNotNone(otp_record)

    def test_delete_account_validation(self):
        self.client.login(username='delete_buyer', password='Password123!')
        # Mismatch username
        payload = {'username': 'wrong_user', 'otp': '123456'}
        response = self.client.post(reverse('delete_account'), json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('confirmation does not match', response.json()['error'])

        # Invalid OTP
        payload = {'username': 'delete_buyer', 'otp': '111111'}
        response = self.client.post(reverse('delete_account'), json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_delete_account_success(self):
        self.client.login(username='delete_buyer', password='Password123!')
        from apps.core.models import EmailOTP
        otp_record = EmailOTP.objects.create(email='delete_buyer@test.com', otp_code='987654')

        payload = {'username': 'delete_buyer', 'otp': '987654'}
        response = self.client.post(reverse('delete_account'), json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='delete_buyer').exists())

    def test_admin_delete_buyer(self):
        # Non-admin try to delete
        self.client.login(username='delete_buyer', password='Password123!')
        response = self.client.post(reverse('admin_delete_buyer', kwargs={'username': 'delete_buyer'}))
        self.assertEqual(response.status_code, 403)

        # Admin delete
        self.client.login(username='admin_user', password='AdminPassword123!')
        response = self.client.post(reverse('admin_delete_buyer', kwargs={'username': 'delete_buyer'}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='delete_buyer').exists())


class OCRValidationTests(TestCase):
    def setUp(self):
        from apps.accounts.models import LandownerApplication
        from datetime import date
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_lo_reviewer',
            email='admin_lo@test.com',
            password='AdminPassword123!',
            role='ADMIN',
            is_verified=True
        )

        dummy_file = SimpleUploadedFile("dummy.jpg", b"file_content", content_type="image/jpeg")

        self.app = LandownerApplication.objects.create(
            first_name='Meet',
            last_name='Sharma',
            date_of_birth=date(1995, 5, 15),
            mobile_number='9876543210',
            email='meet.sharma@test.com',
            aadhaar_number='123456789012',
            pan_number='ABCDE1234F',
            land_name='Green Farms',
            land_address='123 Road',
            state='Punjab',
            district='Amritsar',
            pincode='143001',
            total_area=5.50,
            ownership_details='Ancestral Land',
            aadhaar_document=dummy_file,
            pan_document=dummy_file,
            ownership_document=dummy_file,
            email_verified=True
        )

    def test_ocr_validation_placeholder_created_on_submit(self):
        """Verify the landowner registration view creates a pending OCRValidation record on submit."""
        from apps.accounts.models import OCRValidation
        # Ensure we have a session to mimic the submit workflow
        session = self.client.session
        session['lo_reg_data'] = {
            'first_name': 'Test',
            'last_name': 'Landowner',
            'date_of_birth': '1990-01-01',
            'mobile_number': '9999988888',
            'email': 'new_lo@test.com',
            'aadhaar_number': '987654321098',
            'pan_number': 'XYZAB9876C',
            'land_name': 'Lotus Valley',
            'land_address': 'A-1 Sector 4',
            'state': 'Haryana',
            'district': 'Gurugram',
            'pincode': '122018',
            'total_area': '12.4',
            'ownership_details': 'Self acquired',
            'email_verified': True,
            'aadhaar_document_path': 'temp_lo_app/nosession/aadhaar_document_nosession.jpg',
            'aadhaar_document_name': 'aadhaar.jpg',
            'pan_document_path': 'temp_lo_app/nosession/pan_document_nosession.jpg',
            'pan_document_name': 'pan.jpg',
            'ownership_document_path': 'temp_lo_app/nosession/ownership_document_nosession.jpg',
            'ownership_document_name': 'ownership.jpg',
        }
        session.save()

        # Mock the move of uploaded files and thread start
        from unittest.mock import patch
        with patch('django.core.files.storage.default_storage.exists', return_value=True), \
             patch('django.core.files.storage.default_storage.open'), \
             patch('django.core.files.storage.default_storage.delete'), \
             patch('django.core.mail.send_mail'), \
             patch('threading.Thread') as mock_thread:

            response = self.client.post(reverse('landowner_register_submit'))
            self.assertEqual(response.status_code, 302)

            # Check if pending OCRValidation was created
            from apps.accounts.models import LandownerApplication
            new_app = LandownerApplication.objects.filter(email='new_lo@test.com').first()
            self.assertIsNotNone(new_app)
            self.assertTrue(hasattr(new_app, 'ocr_validation'))
            self.assertEqual(new_app.ocr_validation.validation_status, 'pending')
            self.assertTrue(mock_thread.called)

    def test_pipeline_scoring_all_pass(self):
        """Verify ocr_pipeline scoring gives low risk (score <= 20) on complete pass."""
        from apps.accounts.ocr_pipeline import _run
        from apps.accounts.models import OCRValidation
        from unittest.mock import patch, MagicMock

        ocr_rec = OCRValidation.objects.create(application=self.app, validation_status='pending')

        # Mock image functions & Tesseract
        with patch('apps.accounts.ocr_pipeline._preprocess_image'), \
             patch('apps.accounts.ocr_pipeline._pdf_to_image'), \
             patch('apps.accounts.ocr_pipeline._extract_text') as mock_extract, \
             patch('PIL.Image.open') as mock_image_open:

            mock_image_open.return_value = MagicMock()
            # 1st call for Aadhaar text, 2nd call for PAN text
            mock_extract.side_effect = [
                # Aadhaar raw text & confidence
                ("GOVERNMENT OF INDIA. UIDAI Aadhaar number 1234 5678 9012 Meet Sharma DOB 15/05/1995", 90.0),
                # PAN raw text & confidence
                ("INCOME TAX DEPARTMENT GOVT OF INDIA Permanent Account Number ABCDE1234F Name Meet Sharma DOB 15-05-1995", 85.0)
            ]

            _run(self.app, ocr_rec)

            ocr_rec.refresh_from_db()
            self.assertEqual(ocr_rec.validation_status, 'completed')
            self.assertEqual(ocr_rec.risk_level, 'low')
            self.assertTrue(ocr_rec.aadhaar_doc_type_detected)
            self.assertTrue(ocr_rec.aadhaar_number_found)
            self.assertTrue(ocr_rec.aadhaar_number_match)
            self.assertTrue(ocr_rec.pan_doc_type_detected)
            self.assertTrue(ocr_rec.pan_number_found)
            self.assertTrue(ocr_rec.pan_number_match)
            self.assertEqual(ocr_rec.risk_score, 0)
            self.assertEqual(len(ocr_rec.validation_flags), 0)

    def test_pipeline_scoring_mismatches(self):
        """Verify mismatches (Aadhaar & PAN number discrepancies) trigger High risk and set flags."""
        from apps.accounts.ocr_pipeline import _run
        from apps.accounts.models import OCRValidation
        from unittest.mock import patch, MagicMock

        ocr_rec = OCRValidation.objects.create(application=self.app, validation_status='pending')

        with patch('apps.accounts.ocr_pipeline._preprocess_image'), \
             patch('apps.accounts.ocr_pipeline._pdf_to_image'), \
             patch('apps.accounts.ocr_pipeline._extract_text') as mock_extract, \
             patch('PIL.Image.open') as mock_image_open:

            mock_image_open.return_value = MagicMock()
            # Mismatched Aadhaar (9999...) and mismatched PAN (XYZAB...)
            mock_extract.side_effect = [
                ("UIDAI Aadhaar 9999 9999 9999 Name Meet Sharma DOB 15/05/1995", 80.0),
                ("INCOME TAX DEPT PAN XYZAB9876C Name Meet Sharma DOB 15-05-1995", 80.0)
            ]

            _run(self.app, ocr_rec)

            ocr_rec.refresh_from_db()
            self.assertEqual(ocr_rec.validation_status, 'completed')
            self.assertEqual(ocr_rec.risk_level, 'high')
            self.assertTrue(ocr_rec.aadhaar_number_found)
            self.assertFalse(ocr_rec.aadhaar_number_match)
            self.assertTrue(ocr_rec.pan_number_found)
            self.assertFalse(ocr_rec.pan_number_match)
            # score adds 40 (Aadhaar mismatch) + 40 (PAN mismatch) = 80
            self.assertEqual(ocr_rec.risk_score, 80)
            self.assertEqual(len(ocr_rec.validation_flags), 2)
            self.assertIn("Aadhaar Number Mismatch", ocr_rec.validation_flags[0])
            self.assertIn("PAN Number Mismatch", ocr_rec.validation_flags[1])

    def test_pipeline_graceful_failure(self):
        """Verify pipeline handles tesseract binary failure gracefully by setting status to failed."""
        from apps.accounts.ocr_pipeline import run_ocr_validation
        from apps.accounts.models import OCRValidation
        from unittest.mock import patch

        ocr_rec = OCRValidation.objects.create(application=self.app, validation_status='pending')

        # Trigger run_ocr_validation with mock that raises an exception on PIL image load
        with patch('PIL.Image.open', side_effect=Exception("Tesseract path not found or invalid image")):
            run_ocr_validation(self.app.pk)

            ocr_rec.refresh_from_db()
            self.assertEqual(ocr_rec.validation_status, 'failed')
            self.assertEqual(ocr_rec.risk_level, 'failed')
            self.assertIn("Tesseract path not found", ocr_rec.error_message)


class LandownerOnboardingAndManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.landowner = User.objects.create_user(
            username='rajesh_sharma',
            email='rajesh@example.com',
            password='testpassword123',
            role=User.LAND_OWNER,
            first_name='Rajesh',
            last_name='Sharma',
            is_first_login=True
        )
        self.admin = User.objects.create_superuser(
            username='admin_user',
            email='admin@test.com',
            password='adminpassword123'
        )

    def test_landowner_onboarding_redirection(self):
        """Verify new landowners are redirected to onboarding page on first dashboard request."""
        self.client.force_login(self.landowner)
        response = self.client.get(reverse('landowner_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('onboarding_landowner'), response.url)

    def test_onboarding_skip(self):
        """Verify landowners can skip onboarding, which toggles is_first_login to False."""
        self.client.force_login(self.landowner)
        response = self.client.post(reverse('onboarding_landowner'), data={'action': 'skip'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('landowner_dashboard'), response.url)
        
        self.landowner.refresh_from_db()
        self.assertFalse(self.landowner.is_first_login)

    def test_onboarding_upload_layout(self):
        """Verify landowners can successfully submit a layout, which sets status to uploaded."""
        self.client.force_login(self.landowner)
        from django.core.files.uploadedfile import SimpleUploadedFile
        dummy_pdf = SimpleUploadedFile("layout.pdf", b"pdf content", content_type="application/pdf")
        
        response = self.client.post(reverse('onboarding_landowner'), data={
            'action': 'upload',
            'property_name': 'Green Valley Extension',
            'layout_file': dummy_pdf,
            'notes': 'All plots are east-facing.'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('landowner_dashboard'), response.url)
        
        self.landowner.refresh_from_db()
        self.assertFalse(self.landowner.is_first_login)
        
        from apps.lands.models import SiteLayoutPlan
        layout = SiteLayoutPlan.objects.filter(owner=self.landowner).first()
        self.assertIsNotNone(layout)
        self.assertEqual(layout.property_name, 'Green Valley Extension')
        self.assertEqual(layout.status, 'uploaded')
        self.assertEqual(layout.notes, 'All plots are east-facing.')

    def test_admin_layout_status_progression(self):
        """Verify layout status progression from uploaded to under review and approved."""
        from apps.lands.models import SiteLayoutPlan
        from django.core.files.uploadedfile import SimpleUploadedFile
        dummy_png = SimpleUploadedFile("layout.png", b"png content", content_type="image/png")
        
        layout = SiteLayoutPlan.objects.create(
            owner=self.landowner,
            property_name='Green Valley Extension',
            layout_file=dummy_png,
            notes='Review requested',
            status='uploaded'
        )
        
        # Log in as Admin
        self.client.force_login(self.admin)
        
        # 1. Mark under review
        response = self.client.post(reverse('lands:admin_review_layout', args=[layout.pk]))
        self.assertEqual(response.status_code, 302)
        layout.refresh_from_db()
        self.assertEqual(layout.status, 'under_review')
        
        # 2. Approve & Publish
        from django.core import mail
        response = self.client.post(reverse('lands:admin_approve_layout', args=[layout.pk]))
        self.assertEqual(response.status_code, 302)
        layout.refresh_from_db()
        self.assertEqual(layout.status, 'approved')
        
        # Check system notification was sent to landowner
        from apps.core.models import Notification
        notif = Notification.objects.filter(recipient=self.landowner).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, '🎉 Property Published')
        self.assertIn('Green Valley Extension', notif.message)
        
        # Check email was sent to landowner
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Your property is now live on Lease Monkey')
        self.assertIn('Green Valley Extension', mail.outbox[0].body)

    def test_admin_delete_landowner_cascades(self):
        """Verify admin can delete landowner account, cascading delete to their lands and plots."""
        from apps.lands.models import Land
        land = Land.objects.create(
            name='Green Farms',
            owner=self.landowner,
            location='Malviya Nagar',
            area=5.0,
            average_plot_price=500000.00
        )
        
        # Log in as Admin
        self.client.force_login(self.admin)
        
        # Send delete request
        response = self.client.post(reverse('admin_delete_landowner', args=[self.landowner.username]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'deleted')
        
        # Check user is deleted
        self.assertFalse(User.objects.filter(username=self.landowner.username).exists())
        
        # Check land is deleted (cascaded)
        self.assertFalse(Land.objects.filter(pk=land.pk).exists())


