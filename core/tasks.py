from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import LedgerUpload, Transaction, RiskProfile, Alert
from .risk_engine.processor import process_ledger_file
from .risk_engine.analysis import RiskAnalysisEngine
import logging

logger = logging.getLogger(__name__)

@shared_task
def analyze_transaction(transaction_id):
    """
    Analyze a single transaction for risk.
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        engine = RiskAnalysisEngine()
        risk_score = engine.analyze_transaction(transaction)
        
        # Update transaction risk score
        transaction.risk_score = risk_score
        transaction.save()

        # Update user's risk profile
        profile, _ = RiskProfile.objects.get_or_create(user=transaction.user)
        profile.update_risk_score()

        # Create alert if risk score is high
        if risk_score > 0.8:  # High risk threshold
            Alert.objects.create(
                user=transaction.user,
                transaction=transaction,
                risk_score=risk_score,
                message=f"High risk transaction detected (score: {risk_score:.2f})"
            )
        
        logger.info(f'Successfully analyzed transaction {transaction_id} with risk score {risk_score:.2f}')
        return True
    except Exception as e:
        logger.error(f'Error analyzing transaction {transaction_id}: {str(e)}', exc_info=True)
        return False

@shared_task
def update_all_risk_profiles():
    """
    Periodic task to update all user risk profiles.
    """
    try:
        profiles = RiskProfile.objects.all()
        updated_count = 0
        for profile in profiles:
            profile.update_risk_score()
            updated_count += 1
        logger.info(f'Successfully updated {updated_count} risk profiles')
        return True
    except Exception as e:
        logger.error(f'Error updating risk profiles: {str(e)}', exc_info=True)
        return False

@shared_task
def cleanup_old_alerts(days=30):
    """
    Periodic task to clean up old alerts.
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = Alert.objects.filter(created_at__lt=cutoff_date).delete()[0]
        logger.info(f'Successfully deleted {deleted_count} old alerts')
        return True
    except Exception as e:
        logger.error(f'Error cleaning up old alerts: {str(e)}', exc_info=True)
        return False

@shared_task
def process_ledger_upload(upload_id):
    """
    Celery task to process a ledger upload asynchronously
    """
    try:
        # Get the upload
        upload = LedgerUpload.objects.get(id=upload_id)
        
        # Get file path
        file_path = upload.file.path
        
        # Process the file
        overall_risk, high_risk_count = process_ledger_file(file_path, upload)
        
        logger.info(
            f'Successfully processed ledger upload {upload_id}. '
            f'Risk score: {overall_risk:.2f}, '
            f'High risk transactions: {high_risk_count}'
        )
        
        return True
        
    except LedgerUpload.DoesNotExist:
        logger.error(f'LedgerUpload {upload_id} not found')
        return False
        
    except Exception as e:
        logger.error(f'Error processing ledger upload {upload_id}: {str(e)}', exc_info=True)
        
        # Update upload status
        try:
            upload = LedgerUpload.objects.get(id=upload_id)
            upload.status = 'error'
            upload.error_message = str(e)
            upload.save()
        except Exception as e2:
            logger.error(f'Error updating upload status: {str(e2)}', exc_info=True)
        
        return False