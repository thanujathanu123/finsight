import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ..risk_ml import RiskScorer
from ..rules_engine import compute_risk_scores, parse_ledger_file
import os

class TestRiskAnalysis(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        now = datetime(2025, 11, 5, 14, 30)  # Set fixed datetime for consistent testing
        self.test_data = pd.DataFrame({
            'date': [
                now - timedelta(days=1),
                now - timedelta(hours=2),
                now - timedelta(hours=1),
                now.replace(hour=3),  # Night transaction
                now,
            ],
            'description': [
                'Normal payment',
                'Large transfer',
                'Large transfer',
                'Night withdrawal',
                'Small payment'
            ],
            'amount': [
                100.00,
                15000.00,
                12000.00,
                500.00,
                50.00
            ]
        })
        
        # Custom risk profile for testing
        self.test_profile = {
            'amount_threshold': 10000.00,
            'frequency_threshold': 2,
            'time_window_hours': 24,
            'high_risk_score': 75.0,
            'ml_parameters': {
                'features': ['amount', 'daily_frequency', 'hour_of_day', 'day_of_week']
            }
        }
    
    def test_risk_scorer_initialization(self):
        """Test RiskScorer initialization"""
        scorer = RiskScorer(self.test_profile)
        self.assertFalse(scorer._fitted)
        self.assertEqual(scorer.risk_profile['amount_threshold'], 10000.00)
    
    def test_feature_extraction(self):
        """Test feature extraction from transactions"""
        scorer = RiskScorer(self.test_profile)
        features = scorer._extract_features(self.test_data)
        
        self.assertIn('amount', features.columns)
        self.assertIn('hour_of_day', features.columns)
        self.assertIn('day_of_week', features.columns)
        self.assertIn('daily_frequency', features.columns)
    
    def test_rule_based_scoring(self):
        """Test rule-based risk factor identification"""
        scorer = RiskScorer(self.test_profile)
        
        # Test high amount rule
        high_amount_row = pd.Series({
            'amount': 15000.00,
            'datetime': datetime.now()
        })
        factors = scorer._apply_rules(high_amount_row, {'window_counts': {0: 1}})
        self.assertTrue(any(f['type'] == 'high_amount' for f in factors))
        
        # Test frequency rule
        frequent_row = pd.Series({
            'amount': 100.00,
            'datetime': datetime.now()
        }, name=0)
        factors = scorer._apply_rules(frequent_row, {'window_counts': {0: 6}})
        self.assertTrue(any(f['type'] == 'high_frequency' for f in factors))
    
    def test_complete_scoring(self):
        """Test complete transaction scoring pipeline"""
        # Score transactions
        scored_df, overall_risk = compute_risk_scores(
            self.test_data,
            risk_profile=self.test_profile
        )
        
        # Verify scored DataFrame
        self.assertIn('risk_score', scored_df.columns)
        self.assertIn('risk_factors', scored_df.columns)
        
        # Check high amount transactions are flagged
        high_amount_txns = scored_df[scored_df['amount'] > 10000]
        self.assertTrue(
            all(row['risk_score'] > 75 for _, row in high_amount_txns.iterrows()),
            "High amount transactions should have high risk scores"
        )
        
        # Verify overall risk is between 0 and 100
        self.assertTrue(0 <= overall_risk <= 100)
    
    def test_sample_ledger(self):
        """Test risk scoring with sample ledger file"""
        sample_path = os.path.join(os.path.dirname(__file__), 'sample_ledger.csv')
        if os.path.exists(sample_path):
            # Parse and score sample ledger
            df = parse_ledger_file(sample_path)
            scored_df, overall_risk = compute_risk_scores(df)
            
            # Basic validation
            self.assertGreater(len(scored_df), 0)
            self.assertTrue(0 <= overall_risk <= 100)
            self.assertTrue(all(0 <= score <= 100 for score in scored_df['risk_score']))

if __name__ == '__main__':
    unittest.main()