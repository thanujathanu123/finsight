import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import NotFittedError
import joblib
from datetime import datetime, timedelta
from typing import Tuple, Dict, List
import json
import logging

logger = logging.getLogger(__name__)

class RiskAnalysisEngine:
    """Advanced risk analysis engine using machine learning and rule-based approaches"""
    
    def __init__(self, risk_profile):
        self.risk_profile = risk_profile
        self.model = None
        self.scaler = StandardScaler()
        
        # Load ML parameters from risk profile
        self.ml_params = risk_profile.ml_parameters if risk_profile else {}
        
        # Default parameters if not specified
        self.contamination = self.ml_params.get('contamination', 0.1)
        self.n_estimators = self.ml_params.get('n_estimators', 100)
        self.amount_threshold = float(risk_profile.amount_threshold if risk_profile else 10000)
        self.frequency_threshold = risk_profile.frequency_threshold if risk_profile else 5
        self.time_window = timedelta(hours=risk_profile.time_window_hours if risk_profile else 24)

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract relevant features for risk analysis"""
        features = pd.DataFrame()
        
        # Amount-based features
        features['amount'] = df['amount']
        features['amount_log'] = np.log1p(df['amount'].abs())
        
        # Time-based features
        try:
            df['datetime'] = pd.to_datetime(df['date'])
        except Exception as e:
            logger.warning(f"Error parsing dates: {str(e)}. Attempting various formats...")
            # Try different date formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    df['datetime'] = pd.to_datetime(df['date'], format=fmt)
                    break
                except:
                    continue
            if 'datetime' not in df.columns:
                raise ValueError("Could not parse date column with any known format")
        
        df['hour'] = df['datetime'].dt.hour
        df['day_of_week'] = df['datetime'].dt.dayofweek
        
        # Add hour and day of week features
        features = pd.concat([
            features,
            pd.get_dummies(df['hour'], prefix='hour'),
            pd.get_dummies(df['day_of_week'], prefix='day')
        ], axis=1)
        
        # Transaction frequency features
        for window in [1, 3, 6, 12, 24]:
            # Count transactions in last n hours
            features[f'freq_{window}h'] = df['datetime'].apply(
                lambda x: df[
                    (df['datetime'] >= x - pd.Timedelta(hours=window)) & 
                    (df['datetime'] < x)
                ].shape[0]
            )
        
        # Category-based features
        if 'category' in df.columns:
            features = pd.concat([
                features,
                pd.get_dummies(df['category'], prefix='category')
            ], axis=1)
        
        return features

    def train_model(self, historical_data: pd.DataFrame):
        """Train the anomaly detection model on historical data"""
        features = self.extract_features(historical_data)
        
        # Initialize and train the model
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=42
        )
        
        # Scale features
        scaled_features = self.scaler.fit_transform(features)
        
        # Train model
        self.model.fit(scaled_features)
        
        # Save the model
        joblib.dump(self.model, 'risk_model.joblib')
        joblib.dump(self.scaler, 'risk_scaler.joblib')

    def load_model(self):
        """Load pre-trained model"""
        try:
            self.model = joblib.load('risk_model.joblib')
            self.scaler = joblib.load('risk_scaler.joblib')
        except FileNotFoundError:
            logger.warning("No pre-trained model found. Using default configuration.")
            self.model = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                random_state=42
            )

    def apply_rules(self, transaction: pd.Series) -> List[Dict]:
        """Apply rule-based risk factors"""
        risk_factors = []
        
        # Check amount threshold
        if abs(transaction['amount']) >= self.amount_threshold:
            risk_factors.append({
                'type': 'amount',
                'description': f'Transaction amount (${abs(transaction["amount"]):,.2f}) exceeds threshold (${self.amount_threshold:,.2f})',
                'severity': 'high'
            })
        
        # Check transaction frequency
        if transaction.get('freq_24h', 0) >= self.frequency_threshold:
            risk_factors.append({
                'type': 'frequency',
                'description': f'High transaction frequency: {transaction.get("freq_24h")} transactions in 24 hours',
                'severity': 'medium'
            })
        
        # Check for round amounts (possible structured transactions)
        if abs(transaction['amount']) % 1000 == 0 and abs(transaction['amount']) > 1000:
            risk_factors.append({
                'type': 'pattern',
                'description': 'Round amount transaction detected (possible structuring)',
                'severity': 'medium'
            })
        
        return risk_factors

    def calculate_risk_score(self, anomaly_score: float, risk_factors: List[Dict]) -> float:
        """Calculate final risk score based on anomaly score and risk factors"""
        # Base score from anomaly detection (0-100)
        base_score = (anomaly_score + 1) * 50  # Convert [-1, 1] to [0, 100]
        
        # Add points for each risk factor
        risk_weights = {
            'low': 5,
            'medium': 10,
            'high': 20
        }
        
        factor_score = sum(risk_weights[factor['severity']] for factor in risk_factors)
        
        # Combine scores with weights
        final_score = (0.7 * base_score + 0.3 * factor_score)
        
        # Ensure score is between 0 and 100
        return min(max(final_score, 0), 100)

    def analyze_transaction(self, transaction: pd.Series) -> Tuple[float, List[Dict]]:
        """Analyze a single transaction for risk"""
        # Extract features
        features = self.extract_features(pd.DataFrame([transaction]))
        
        # Scale features
        scaled_features = self.scaler.transform(features)
        
        # Get anomaly score
        anomaly_score = self.model.score_samples(scaled_features)[0]
        
        # Apply rule-based factors
        risk_factors = self.apply_rules(transaction)
        
        # Calculate final risk score
        risk_score = self.calculate_risk_score(anomaly_score, risk_factors)
        
        return risk_score, risk_factors

    def analyze_transactions(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
        """Analyze multiple transactions and return risk scores"""
        if self.model is None:
            self.load_model()
        
        # Extract features for all transactions
        features = self.extract_features(df)
        
        # Scale features with fallback fitting if needed
        try:
            scaled_features = self.scaler.transform(features)
        except NotFittedError:
            scaled_features = self.scaler.fit_transform(features)
        
        # Ensure the model is fitted before scoring
        try:
            anomaly_scores = self.model.score_samples(scaled_features)
        except NotFittedError:
            self.model.fit(scaled_features)
            anomaly_scores = self.model.score_samples(scaled_features)
        
        # Calculate risk factors and scores for each transaction
        results = []
        for idx, row in df.iterrows():
            risk_factors = self.apply_rules(row)
            risk_score = self.calculate_risk_score(anomaly_scores[idx], risk_factors)
            results.append({
                'risk_score': risk_score,
                'risk_factors': risk_factors
            })
        
        # Add results to dataframe
        df['risk_score'] = [r['risk_score'] for r in results]
        df['risk_factors'] = [json.dumps(r['risk_factors']) for r in results]
        
        # Calculate overall risk score for the batch
        overall_risk = np.mean(df['risk_score']) + (np.std(df['risk_score']) * 0.1)
        
        return df, min(overall_risk, 100)