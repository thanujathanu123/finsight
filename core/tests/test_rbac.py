from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group

class RBACTestCase(TestCase):
    def setUp(self):
        # Create test users for each role
        self.roles = {
            'admin': 'Admin',
            'auditor': 'Auditor',
            'finance': 'FinanceOfficer',
            'reviewer': 'Reviewer',
            'guest': 'Guest'
        }
        
        self.users = {}
        self.clients = {}
        
        # Create groups if they don't exist
        for role_name in self.roles.values():
            Group.objects.get_or_create(name=role_name)
        
        # Create users and assign to groups
        for username, role in self.roles.items():
            user = User.objects.create_user(
                username=f'test_{username}',
                password='test123'
            )
            group = Group.objects.get(name=role)
            user.groups.add(group)
            self.users[username] = user
            
            # Create a client for this user
            client = Client()
            client.login(username=f'test_{username}', password='test123')
            self.clients[username] = client

    def test_admin_access(self):
        """Test Admin user access to all dashboards"""
        client = self.clients['admin']
        
        # Admin should have access to all dashboards
        dashboards = ['admin_dashboard', 'auditor_dashboard', 
                     'finance_dashboard', 'reviewer_dashboard']
        
        for dashboard in dashboards:
            response = client.get(reverse(dashboard))
            self.assertEqual(response.status_code, 200, 
                           f'Admin should have access to {dashboard}')

    def test_auditor_access(self):
        """Test Auditor access permissions"""
        client = self.clients['auditor']
        
        # Should have access to
        self.assertEqual(
            client.get(reverse('auditor_dashboard')).status_code, 
            200, 
            'Auditor should have access to auditor dashboard'
        )
        self.assertEqual(
            client.get(reverse('upload_ledger')).status_code, 
            200, 
            'Auditor should have access to upload ledger'
        )
        
        # Should not have access to
        self.assertNotEqual(
            client.get(reverse('admin_dashboard')).status_code, 
            200, 
            'Auditor should not have access to admin dashboard'
        )

    def test_finance_officer_access(self):
        """Test Finance Officer access permissions"""
        client = self.clients['finance']
        
        # Should have access to
        self.assertEqual(
            client.get(reverse('finance_dashboard')).status_code, 
            200, 
            'Finance Officer should have access to finance dashboard'
        )
        self.assertEqual(
            client.get(reverse('upload_ledger')).status_code, 
            200, 
            'Finance Officer should have access to upload ledger'
        )
        
        # Should not have access to
        self.assertNotEqual(
            client.get(reverse('admin_dashboard')).status_code, 
            200, 
            'Finance Officer should not have access to admin dashboard'
        )
        self.assertNotEqual(
            client.get(reverse('auditor_dashboard')).status_code, 
            200, 
            'Finance Officer should not have access to auditor dashboard'
        )

    def test_reviewer_access(self):
        """Test Reviewer access permissions"""
        client = self.clients['reviewer']
        
        # Should have access to
        self.assertEqual(
            client.get(reverse('reviewer_dashboard')).status_code, 
            200, 
            'Reviewer should have access to reviewer dashboard'
        )
        
        # Should not have access to
        self.assertNotEqual(
            client.get(reverse('admin_dashboard')).status_code, 
            200, 
            'Reviewer should not have access to admin dashboard'
        )
        self.assertNotEqual(
            client.get(reverse('upload_ledger')).status_code, 
            200, 
            'Reviewer should not have access to upload ledger'
        )

    def test_guest_access(self):
        """Test Guest access permissions"""
        client = self.clients['guest']
        
        # Should have access to
        self.assertEqual(
            client.get(reverse('guest_dashboard')).status_code, 
            200, 
            'Guest should have access to guest dashboard'
        )
        
        # Should not have access to
        restricted_urls = [
            'admin_dashboard', 'auditor_dashboard',
            'finance_dashboard', 'reviewer_dashboard',
            'upload_ledger'
        ]
        
        for url in restricted_urls:
            self.assertNotEqual(
                client.get(reverse(url)).status_code, 
                200, 
                f'Guest should not have access to {url}'
            )

    def test_unauthenticated_access(self):
        """Test unauthenticated user access"""
        client = Client()  # Unauthenticated client
        
        # Should have access to
        self.assertEqual(
            client.get(reverse('guest_dashboard')).status_code, 
            200, 
            'Unauthenticated users should have access to guest dashboard'
        )
        self.assertEqual(
            client.get(reverse('login')).status_code, 
            200, 
            'Unauthenticated users should have access to login page'
        )
        
        # Should not have access to protected pages
        protected_urls = [
            'admin_dashboard', 'auditor_dashboard',
            'finance_dashboard', 'reviewer_dashboard',
            'upload_ledger'
        ]
        
        for url in protected_urls:
            response = client.get(reverse(url))
            self.assertIn(response.status_code, [302, 403], 
                         f'Unauthenticated users should not have access to {url}')