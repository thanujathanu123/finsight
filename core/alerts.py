"""Alert generation and management system"""
from django.db import transaction
from django.utils import timezone
from .models import Alert, Transaction, User
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class AlertRule:
    """Base class for alert rules"""
    def __init__(self, name: str, description: str, severity: str):
        self.name = name
        self.description = description
        self.severity = severity

    def evaluate(self, transaction: Transaction) -> bool:
        raise NotImplementedError("Subclasses must implement evaluate()")

    def create_alert(self, transaction: Transaction, created_by: User) -> Alert:
        return Alert.objects.create(
            title=self.name,
            description=self.description.format(
                amount=transaction.amount,
                date=transaction.date.strftime("%Y-%m-%d %H:%M:%S"),
                description=transaction.description,
                risk_score=transaction.risk_score
            ),
            severity=self.severity,
            transaction=transaction,
            created_by=created_by
        )

class HighRiskRule(AlertRule):
    """Alert on high risk transactions"""
    def __init__(self):
        super().__init__(
            name="High Risk Transaction",
            description="Transaction of ${amount:,.2f} on {date} has a high risk score of {risk_score:.1f}",
            severity="high"
        )

    def evaluate(self, transaction: Transaction) -> bool:
        return transaction.risk_score > 90

class LargeAmountRule(AlertRule):
    """Alert on unusually large transactions"""
    def __init__(self, threshold: float = 10000.0):
        super().__init__(
            name="Large Transaction",
            description="Large transaction of ${amount:,.2f} detected on {date}",
            severity="medium"
        )
        self.threshold = threshold

    def evaluate(self, transaction: Transaction) -> bool:
        return abs(transaction.amount) >= self.threshold

class RapidFrequencyRule(AlertRule):
    """Alert on high frequency of transactions"""
    def __init__(self, threshold: int = 5, hours: int = 24):
        super().__init__(
            name="High Transaction Frequency",
            description="Multiple transactions detected within {hours} hours",
            severity="medium"
        )
        self.threshold = threshold
        self.hours = hours

    def evaluate(self, transaction: Transaction) -> bool:
        time_window = transaction.date - timezone.timedelta(hours=self.hours)
        count = Transaction.objects.filter(
            date__gt=time_window,
            date__lte=transaction.date
        ).count()
        return count >= self.threshold

def get_alert_rules() -> List[AlertRule]:
    """Get list of all alert rules"""
    return [
        HighRiskRule(),
        LargeAmountRule(),
        RapidFrequencyRule()
    ]

def process_alerts(transaction: Transaction, created_by: User) -> List[Alert]:
    """Process all alert rules for a transaction"""
    alerts = []
    rules = get_alert_rules()

    with transaction.atomic():
        for rule in rules:
            try:
                if rule.evaluate(transaction):
                    alert = rule.create_alert(transaction, created_by)
                    alerts.append(alert)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {str(e)}")
                continue

    return alerts

def assign_alerts(alerts: List[Alert]) -> None:
    """Assign alerts to reviewers based on workload"""
    from django.contrib.auth.models import Group
    
    if not alerts:
        return

    # Get all active reviewers
    reviewer_group = Group.objects.get(name='Reviewer')
    reviewers = User.objects.filter(groups=reviewer_group, is_active=True)
    
    if not reviewers:
        logger.warning("No active reviewers found for alert assignment")
        return

    # Get current workload for each reviewer
    workload = {
        reviewer.id: Alert.objects.filter(
            assigned_to=reviewer,
            status__in=['new', 'in_progress']
        ).count()
        for reviewer in reviewers
    }

    # Assign alerts to reviewers with lowest workload
    for alert in alerts:
        if not alert.assigned_to:
            # Find reviewer with lowest workload
            reviewer_id = min(workload, key=workload.get)
            reviewer = next(r for r in reviewers if r.id == reviewer_id)
            
            # Assign alert
            alert.assigned_to = reviewer
            alert.save()
            
            # Update workload
            workload[reviewer_id] += 1