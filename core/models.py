from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
import uuid


class RiskProfile(models.Model):
    """Configurable risk thresholds and rules"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    industry = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    
    # Risk thresholds
    amount_threshold = models.DecimalField(
        max_digits=15, decimal_places=2, 
        help_text="Transaction amount that triggers heightened scrutiny"
    )
    frequency_threshold = models.IntegerField(
        help_text="Number of transactions within time window that triggers alerts"
    )
    time_window_hours = models.IntegerField(
        help_text="Time window for frequency analysis (in hours)"
    )
    
    # ML model parameters (stored as JSON)
    ml_parameters = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} v{self.version}"


class Transaction(models.Model):
    """Financial transaction with risk scoring"""
    CATEGORIES = [
        ('payment', 'Payment'),
        ('transfer', 'Transfer'),
        ('withdrawal', 'Withdrawal'),
        ('deposit', 'Deposit'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('flagged', 'Flagged for Review'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateTimeField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORIES)
    reference_id = models.CharField(max_length=100, unique=True)
    
    # Risk assessment
    risk_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 risk score, higher means more risky"
    )
    risk_factors = models.JSONField(
        default=dict,
        help_text="Factors contributing to risk score"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ledger_upload = models.ForeignKey('LedgerUpload', on_delete=models.CASCADE)
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='reviewed_transactions'
    )
    
    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date', 'risk_score']),
            models.Index(fields=['status', 'risk_score']),
        ]

    def __str__(self):
        return f"{self.reference_id} - {self.amount} ({self.status})"


class Alert(models.Model):
    """Risk-based alerts and notifications"""
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Relations
    transaction = models.ForeignKey(
        Transaction, 
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_alerts'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_alerts'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.severity} - {self.title} ({self.status})"


class AuditLog(models.Model):
    """Comprehensive activity logging"""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('login', 'Login'),
        ('logout', 'Logout'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=200)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.action} {self.model_name} at {self.timestamp}"


class LedgerUpload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Analysis'),
        ('processing', 'Processing'),
        ('completed', 'Analysis Complete'),
        ('error', 'Error'),
    ]
    
    file = models.FileField(
        upload_to='ledgers/',
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'xlsx'])]
    )
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField(blank=True)
    
    # Risk analysis results
    risk_score = models.FloatField(null=True, blank=True)
    risk_factors = models.JSONField(default=dict)
    transaction_count = models.IntegerField(default=0)
    high_risk_count = models.IntegerField(default=0)
    
    # Processing metadata
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.DurationField(null=True, blank=True)
    
    # Risk profile used
    risk_profile = models.ForeignKey(
        RiskProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Risk profile used for analysis"
    )
    
    def __str__(self):
        return f"{self.filename} by {self.uploaded_by} ({self.status})"

    class Meta:
        ordering = ['-uploaded_at']
