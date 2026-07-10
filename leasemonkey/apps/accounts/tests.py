from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import UserPreferences

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
