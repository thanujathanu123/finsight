import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pandas as pd
from typing import Dict, Tuple, List, Optional
from datetime import datetime, timedelta

class RiskScorer:
    """Combined ML and rules-based risk scoring engine"""
    
    def __init__(self, risk_profile=None):
        self.risk_profile = risk_profile or self._default_risk_profile()
        self.scaler = StandardScaler()
        self.isolation_forest = IsolationForest(
            contamination=0.1,  # Expect ~10% anomalies
            random_state=42,    # For reproducibility
            n_estimators=100
        )
        self._fitted = False
    
    def _default_risk_profile(self) -> Dict:
        """Default risk thresholds if no profile provided"""
        return {
            'amount_threshold': 10000.00,
            'frequency_threshold': 5,
            'time_window_hours': 24,
            'high_risk_score': 75.0,
            'ml_parameters': {
                'features': [
                    'amount',
                    'daily_frequency',
                    'hour_of_day',
                    'day_of_week'
                ]
            }
        }
    
    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract features for ML analysis"""
        features = pd.DataFrame()
        
        # Amount feature
        features['amount'] = df['amount'].astype(float)
        
        # Time-based features
        if 'datetime' not in df.columns and 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'])
        elif 'datetime' not in df.columns:
            raise ValueError("No datetime or date column found in data")
            
        features['hour_of_day'] = df['datetime'].dt.hour
        features['day_of_week'] = df['datetime'].dt.dayofweek
        
        # Transaction frequency
        daily_counts = df.groupby(df['datetime'].dt.date)['amount'].count()
        features['daily_frequency'] = df['datetime'].dt.date.map(daily_counts)
        
        return features
    
    def _apply_rules(self, row: pd.Series, context: Dict) -> List[Dict]:
        """Apply business rules to identify risk factors"""
        risk_factors = []
        
        # High amount rule
        if row['amount'] > self.risk_profile['amount_threshold']:
            risk_factors.append({
                'type': 'high_amount',
                'severity': 'high',
                'details': f"Amount ${row['amount']:,.2f} exceeds threshold ${self.risk_profile['amount_threshold']:,.2f}"
            })
        
        # Frequency rule - check transactions within time window
        if 'datetime' in row:
            time_window = row['datetime'] - timedelta(hours=self.risk_profile['time_window_hours'])
            window_count = context['window_counts'].get(row.name, 0)
            
            if window_count > self.risk_profile['frequency_threshold']:
                risk_factors.append({
                    'type': 'high_frequency',
                    'severity': 'medium',
                    'details': f"{window_count} transactions in {self.risk_profile['time_window_hours']}h window"
                })
            
            # Time-based rules
            hour = row['datetime'].hour
            if hour < 6 or hour > 22:
                risk_factors.append({
                    'type': 'unusual_time',
                    'severity': 'low',
                    'details': f"Transaction at {hour:02d}:00 outside normal hours"
                })
        
        return risk_factors
    
    def _compute_window_counts(self, df: pd.DataFrame) -> Dict:
        """Pre-compute transaction counts within rolling windows"""
        window_counts = {}
        df = df.sort_values('datetime')  # Ensure chronological order
        
        for idx, row in df.iterrows():
            time_window = row['datetime'] - timedelta(hours=self.risk_profile['time_window_hours'])
            window_mask = (
                (df['datetime'] > time_window) & 
                (df['datetime'] < row['datetime'])  # Change <= to < to not count current transaction
            )
            count = window_mask.sum()
            window_counts[idx] = count + 1  # Add 1 to include current transaction
        
        return window_counts
    
    def fit(self, historical_data: pd.DataFrame):
        """Fit the ML model on historical transaction data"""
        if historical_data.empty:
            raise ValueError("Cannot fit on empty dataset")
            
        features = self._extract_features(historical_data)
        self.scaler.fit(features)
        scaled_features = self.scaler.transform(features)
        self.isolation_forest.fit(scaled_features)
        self._fitted = True
        
        return self
    
    def score_transactions(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
        """Score transactions and return risk details"""
        if df.empty:
            return df, 0.0
        
        # Extract and scale features
        features = self._extract_features(df)
        if self._fitted:
            scaled_features = self.scaler.transform(features)
        else:
            # If not fitted, fit on this data (not ideal but workable)
            scaled_features = self.scaler.fit_transform(features)
            self.isolation_forest.fit(scaled_features)
            self._fitted = True
        
        # Get anomaly scores from IsolationForest
        # Convert from {-1, 1} to [0, 1] range where 1 is most anomalous
        ml_scores = (1 - (self.isolation_forest.score_samples(scaled_features) + 1) / 2) * 100
        
        # Pre-compute window counts for frequency analysis
        window_counts = self._compute_window_counts(df)
        
        # Apply rules and combine with ML scores
        results = []
        for idx, row in df.iterrows():
            # Get rule-based risk factors
            risk_factors = self._apply_rules(row, {'window_counts': window_counts})
            
            # Combine ML and rules-based scoring
            ml_score = ml_scores[idx]
            # Score based on risk factor severity
            rules_score = 0
            for factor in risk_factors:
                if factor['severity'] == 'high':
                    rules_score += 80  # Increased from 50 to 80
                elif factor['severity'] == 'medium':
                    rules_score += 50  # Increased from 30 to 50
                else:  # low severity
                    rules_score += 25  # Increased from 15 to 25
            rules_score = min(100, rules_score)
            
            # For high amounts, take max of ML and rules score to ensure high risk
            if row['amount'] > self.risk_profile['amount_threshold']:
                final_score = max(ml_score, rules_score, 80.0)  # Force minimum 80 for high amounts
            else:
                # Normal weighting for regular transactions
                rules_weight = 0.4
                ml_weight = 0.6
                final_score = (ml_weight * ml_score) + (rules_weight * rules_score)
            
            results.append({
                'risk_score': final_score,
                'risk_factors': risk_factors,
                'ml_score': ml_score,
                'rules_score': rules_score
            })
        
        # Create results DataFrame
        results_df = pd.DataFrame(results)
        df = pd.concat([df, results_df], axis=1)
        
        # Calculate overall risk score (weighted by amount)
        total_amount = df['amount'].sum()
        overall_risk = (
            (df['risk_score'] * df['amount']).sum() / total_amount
            if total_amount > 0 else 0.0
        )
        
        return df, overall_risk
    
    def analyze_ledger(self, df: pd.DataFrame) -> Dict:
        """Analyze a complete ledger and return summary statistics"""
        scored_df, overall_risk = self.score_transactions(df)
        
        high_risk_threshold = self.risk_profile['high_risk_score']
        high_risk_txns = scored_df[scored_df['risk_score'] >= high_risk_threshold]
        
        return {
            'overall_risk': overall_risk,
            'transaction_count': len(df),
            'high_risk_count': len(high_risk_txns),
            'risk_factors': self._summarize_risk_factors(scored_df),
            'scored_transactions': scored_df
        }
    
    def _summarize_risk_factors(self, scored_df: pd.DataFrame) -> Dict:
        """Summarize risk factors across all transactions"""
        all_factors = []
        for factors in scored_df['risk_factors']:
            all_factors.extend(factors)
            
        summary = {
            'high_amount': 0,
            'high_frequency': 0,
            'unusual_time': 0
        }
        
        for factor in all_factors:
            if factor['type'] in summary:
                summary[factor['type']] += 1
        
        return summary