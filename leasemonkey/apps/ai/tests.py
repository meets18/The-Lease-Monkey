import json
from unittest.mock import patch
import requests
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.lands.models import Land, Plot
from apps.accounts.models import UserPreferences
from .models import ChatSession, ChatMessage, SupportTicket

User = get_user_model()

class AiAssistantTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create user
        self.user = User.objects.create_user(
            username='buyertest',
            email='buyertest@test.com',
            password='testpassword123',
            role='BUYER'
        )
        self.admin = User.objects.create_user(
            username='admintest',
            email='admintest@test.com',
            password='testpassword123',
            role='ADMIN'
        )
        # Create Land and Plots
        self.land = Land.objects.create(
            name='Test Valley',
            owner=self.admin,
            area=12.5,
            average_plot_price=500000.0,
            location='Jaipur'
        )
        self.plot = Plot.objects.create(
            land=self.land,
            plot_number='A1',
            area='1500 sqft',
            price=450000.0,
            facing='North',
            status='available',
            coordinates=[[0,0], [0,1], [1,1], [1,0]]
        )

    def test_chat_session_creation(self):
        """Test that sending a message creates a session and message log."""
        self.client.force_login(self.user)
        url = reverse('ai:send_chat_message')
        
        with patch('requests.post') as mock_post:
            # Mock successful response from local Ollama
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'response': 'Hello, I am Ollama!'}
            
            response = self.client.post(
                url,
                data=json.dumps({'message': 'Hi, how are you?'}),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            res_data = response.json()
            self.assertIn('session_id', res_data)
            self.assertEqual(res_data['response'], 'Hello, I am Ollama!')
            
            # Check DB
            self.assertEqual(ChatSession.objects.count(), 1)
            self.assertEqual(ChatMessage.objects.count(), 2) # 1 user, 1 AI

    def test_recommendation_trigger(self):
        """Test that recommendation queries include context matching user preferences."""
        self.client.force_login(self.user)
        # Configure user preferences
        pref = UserPreferences.objects.get(user=self.user)
        pref.max_budget = 600000.0
        pref.save()

        url = reverse('ai:send_chat_message')
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'response': 'Recommendation generated'}
            
            response = self.client.post(
                url,
                data=json.dumps({'message': 'Could you recommend me a plot matching my budget?'}),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            mock_post.assert_called_once()
            # Verify system prompt in POST call contains preferences and plot context
            sent_payload = mock_post.call_args[1]['json']
            self.assertIn('CONTEXT FOR RECOMMENDATIONS', sent_payload['system'])
            self.assertIn('Plot Number: A1', sent_payload['system'])
            self.assertIn('User Budget Range: 0 to 600000.00 INR', sent_payload['system'])

    def test_graceful_degradation_and_ollama_errors(self):
        """Test that multiple consecutive Ollama request exceptions return offline message without creating tickets."""
        self.client.force_login(self.user)
        url = reverse('ai:send_chat_message')
        
        with patch('requests.post', side_effect=requests.exceptions.RequestException("Timeout")):
            # First error
            response = self.client.post(
                url,
                data=json.dumps({'message': 'Tell me how meetings work.'}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()['ticket_created'])
            self.assertEqual(response.json()['consecutive_errors'], 1)
            self.assertIn("temporarily offline", response.json()['response'])
            
            # Second error
            response2 = self.client.post(
                url,
                data=json.dumps({'message': 'Is the system online?'}),
                content_type='application/json'
            )
            self.assertEqual(response2.status_code, 200)
            self.assertFalse(response2.json()['ticket_created'])
            self.assertEqual(response2.json()['consecutive_errors'], 2)
            self.assertIn("offline due to heavy load", response2.json()['response'])
            self.assertEqual(SupportTicket.objects.count(), 0)

    def test_resolve_support_ticket(self):
        """Test that the admin resolve ticket view updates ticket status."""
        ticket = SupportTicket.objects.create(
            user=self.user,
            user_query='Login loop bug'
        )
        url = reverse('ai:resolve_ticket', args=[ticket.id])
        
        # Test unauthorized non-admin access
        self.client.force_login(self.user)
        response = self.client.post(url, data=json.dumps({'admin_notes': 'fixed'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        
        # Test admin resolution
        self.client.force_login(self.admin)
        response = self.client.post(url, data=json.dumps({'admin_notes': 'Resolved database locking issue.'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'RESOLVED')
        self.assertEqual(ticket.admin_notes, 'Resolved database locking issue.')
        self.assertIsNotNone(ticket.resolved_at)
