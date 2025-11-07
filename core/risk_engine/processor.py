import pandas as pd
from typing import Tuple
import logging
from .analysis import RiskAnalysisEngine
from ..models import Transaction, Alert, RiskProfile, LedgerUpload
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User, Group

logger = logging.getLogger(__name__)

def process_ledger_file(file_path: str, ledger_upload: LedgerUpload) -> Tuple[float, int]:
    """
    Process a ledger file and analyze transactions for risk.
    Returns (overall_risk_score, high_risk_count)
    """
    try:
        # Read the file based on extension
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, parse_dates=['date'])
        elif file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path, parse_dates=['date'])
        else:
            raise ValueError("Unsupported file format")
        
        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            try:
                df['date'] = pd.to_datetime(df['date'])
            except Exception as e:
                raise ValueError(f"Could not parse date column: {str(e)}")

        # Ensure required columns exist
        required_columns = ['date', 'amount', 'description']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"Missing required columns: {required_columns}")

        # Get or create default risk profile if none specified
        risk_profile = ledger_upload.risk_profile or RiskProfile.objects.filter(is_active=True).first()
        if not risk_profile:
            risk_profile = RiskProfile.objects.create(
                name="Default Profile",
                description="Auto-generated default risk profile",
                industry="General",
                amount_threshold=10000,
                frequency_threshold=5,
                time_window_hours=24,
                created_by=ledger_upload.uploaded_by
            )

        # Initialize risk analysis engine
        engine = RiskAnalysisEngine(risk_profile)

        # Analyze transactions
        start_time = timezone.now()
        scored_df, overall_risk = engine.analyze_transactions(df)
        processing_time = timezone.now() - start_time

        # Count high risk transactions (risk score > 70)
        high_risk_count = len(scored_df[scored_df['risk_score'] > 70])

        # Update ledger upload record
        ledger_upload.status = 'completed'
        ledger_upload.risk_score = overall_risk
        ledger_upload.high_risk_count = high_risk_count
        ledger_upload.transaction_count = len(df)
        ledger_upload.processed_at = timezone.now()
        ledger_upload.processing_time = processing_time
        ledger_upload.risk_profile = risk_profile
        ledger_upload.save()

        # Create Transaction records and alerts
        with transaction.atomic():
            for _, row in scored_df.iterrows():
                # Create transaction record
                trans = Transaction.objects.create(
                    date=row['date'],
                    amount=row['amount'],
                    description=row['description'],
                    category=row.get('category', 'other'),
                    reference_id=row.get('reference_id', f"TX-{timezone.now().timestamp()}"),
                    risk_score=row['risk_score'],
                    risk_factors=row['risk_factors'],
                    ledger_upload=ledger_upload,
                    status='flagged' if row['risk_score'] > 70 else 'pending'
                )

                # Create alert for high-risk transactions
                if row['risk_score'] > 70:
                    Alert.objects.create(
                        title=f"High Risk Transaction Detected",
                        description=f"Transaction {trans.reference_id} has a risk score of {row['risk_score']:.1f}",
                        severity='high' if row['risk_score'] > 90 else 'medium',
                        transaction=trans,
                        created_by=ledger_upload.uploaded_by
                    )

        # Assign alerts to reviewers
        assign_alerts_to_reviewers()

        return overall_risk, high_risk_count

    except Exception as e:
        logger.error(f"Error processing ledger file: {str(e)}", exc_info=True)
        ledger_upload.status = 'error'
        ledger_upload.error_message = str(e)
        ledger_upload.save()
        raise

def assign_alerts_to_reviewers():
    """Distribute unassigned alerts among available reviewers"""
    try:
        # Get unassigned alerts
        unassigned_alerts = Alert.objects.filter(assigned_to__isnull=True)
        if not unassigned_alerts.exists():
            return

        # Get available reviewers
        reviewer_group = Group.objects.get(name='Reviewer')
        reviewers = User.objects.filter(groups=reviewer_group, is_active=True)
        if not reviewers.exists():
            return

        # Distribute alerts among reviewers
        for idx, alert in enumerate(unassigned_alerts):
            reviewer = reviewers[idx % len(reviewers)]
            alert.assigned_to = reviewer
            alert.save()

    except Exception as e:
        logger.error(f"Error assigning alerts to reviewers: {str(e)}", exc_info=True)
        raise