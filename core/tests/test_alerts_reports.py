"""Unit tests for alerts and reports"""
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.utils import timezone
from core.models import Transaction, Alert, RiskProfile, LedgerUpload
from core.alerts import process_alerts, assign_alerts
from core.reports import generate_report
from datetime import timedelta
from decimal import Decimal
import json

class AlertsTestCase(TestCase):
    def setUp(self):
        # Create test users and groups
        self.reviewer_group = Group.objects.create(name='Reviewer')
        self.admin_user = User.objects.create_user('admin', 'admin@test.com', 'adminpass')
        self.reviewer1 = User.objects.create_user('reviewer1', 'rev1@test.com', 'rev1pass')
        self.reviewer2 = User.objects.create_user('reviewer2', 'rev2@test.com', 'rev2pass')
        
        self.reviewer1.groups.add(self.reviewer_group)
        self.reviewer2.groups.add(self.reviewer_group)
        
        # Create test risk profile
        self.risk_profile = RiskProfile.objects.create(
            name="Test Profile",
            description="Test Risk Profile",
            industry="Testing",
            amount_threshold=10000,
            frequency_threshold=5,
            time_window_hours=24,
            created_by=self.admin_user
        )
        
        # Create test ledger upload
        self.ledger = LedgerUpload.objects.create(
            file='test.csv',
            filename='test.csv',
            uploaded_by=self.admin_user,
            status='completed',
            risk_profile=self.risk_profile
        )
        
        # Create test transactions
        self.high_risk_tx = Transaction.objects.create(
            date=timezone.now(),
            amount=15000,
            description="High risk test transaction",
            category='transfer',
            reference_id='TEST-001',
            risk_score=95,
            ledger_upload=self.ledger
        )
        
        self.low_risk_tx = Transaction.objects.create(
            date=timezone.now(),
            amount=100,
            description="Low risk test transaction",
            category='payment',
            reference_id='TEST-002',
            risk_score=20,
            ledger_upload=self.ledger
        )
    
    def test_alert_generation(self):
        """Test alert generation for high-risk transactions"""
        # Process alerts for high-risk transaction
        alerts = process_alerts(self.high_risk_tx, self.admin_user)
        
        # Verify alerts were created
        self.assertTrue(len(alerts) > 0)
        self.assertEqual(alerts[0].severity, 'high')
        self.assertEqual(alerts[0].transaction, self.high_risk_tx)
        
        # Process alerts for low-risk transaction
        alerts = process_alerts(self.low_risk_tx, self.admin_user)
        
        # Verify no alerts were created
        self.assertEqual(len(alerts), 0)
    
    def test_alert_assignment(self):
        """Test alert assignment to reviewers"""
        # Create some alerts
        alerts = [
            Alert.objects.create(
                title=f"Test Alert {i}",
                description="Test alert description",
                severity='high',
                transaction=self.high_risk_tx,
                created_by=self.admin_user
            )
            for i in range(5)
        ]
        
        # Assign alerts
        assign_alerts(alerts)
        
        # Verify assignments
        self.assertEqual(
            Alert.objects.filter(assigned_to=self.reviewer1).count(),
            3  # Should get 3 alerts
        )
        self.assertEqual(
            Alert.objects.filter(assigned_to=self.reviewer2).count(),
            2  # Should get 2 alerts
        )

class ReportsTestCase(TestCase):
    def setUp(self):
        # Create test data similar to AlertsTestCase
        self.admin_user = User.objects.create_user('admin', 'admin@test.com', 'adminpass')
        self.risk_profile = RiskProfile.objects.create(
            name="Test Profile",
            description="Test Risk Profile",
            industry="Testing",
            amount_threshold=10000,
            frequency_threshold=5,
            time_window_hours=24,
            created_by=self.admin_user
        )
        
        self.ledger = LedgerUpload.objects.create(
            file='test.csv',
            filename='test.csv',
            uploaded_by=self.admin_user,
            status='completed',
            risk_profile=self.risk_profile
        )
        
        # Create transactions over several days
        base_date = timezone.now() - timedelta(days=7)
        for i in range(10):
            Transaction.objects.create(
                date=base_date + timedelta(days=i),
                amount=Decimal(str(1000 * (i + 1))),
                description=f"Test transaction {i+1}",
                category='payment',
                reference_id=f'TEST-{i+1:03d}',
                risk_score=float(i * 10),
                ledger_upload=self.ledger
            )
    
    def test_risk_analysis_report(self):
        """Test risk analysis report generation"""
        response = generate_report('risk_analysis', format='pdf')
        
        # Verify PDF was generated
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))
        
        # Generate CSV format
        response = generate_report('risk_analysis', format='csv')
        
        # Verify CSV was generated
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))
    
    def test_activity_report(self):
        """Test activity report generation"""
        response = generate_report('activity', format='pdf')
        
        # Verify PDF was generated
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))
        
        # Generate CSV format
        response = generate_report('activity', format='csv')
        
        # Verify CSV was generated
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))