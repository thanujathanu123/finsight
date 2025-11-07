from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q, F, ExpressionWrapper, DurationField
from django.urls import reverse
from .forms import (
    UserRegistrationForm,
    UploadLedgerForm,
    UserActivationForm,
    UserRoleUpdateForm,
)
import os
from .models import LedgerUpload, Transaction, Alert, RiskProfile, AuditLog
from django.views.decorators.http import require_POST
from .risk_engine.processor import process_ledger_file


def _determine_risk_class(score):
    if score is None:
        return 'risk-low'
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        return 'risk-low'
    if numeric_score >= 70:
        return 'risk-high'
    if numeric_score >= 40:
        return 'risk-medium'
    return 'risk-low'


def _format_duration(duration_value):
    if not duration_value:
        return None
    total_seconds = int(duration_value.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def is_in_group(user, group_name):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return group_name != 'Guest'
    return user.groups.filter(name=group_name).exists()


def can_upload_ledger(user):
    """Check if user can upload ledgers (Admin, Auditor, or FinanceOfficer)"""
    return any(is_in_group(user, role) for role in ['Admin', 'Auditor', 'FinanceOfficer'])


def role_redirect(user):
    if user.is_superuser or is_in_group(user, 'Admin'):
        return 'admin_dashboard'
    if is_in_group(user, 'Auditor'):
        return 'auditor_dashboard'
    if is_in_group(user, 'FinanceOfficer'):
        return 'finance_dashboard'
    if is_in_group(user, 'Reviewer'):
        return 'reviewer_dashboard'
    return 'guest_dashboard'


def has_admin_access(user):
    """Check if the user has permissions for admin-only management features."""
    return user.is_superuser or is_in_group(user, 'Admin')


@login_required
@user_passes_test(has_admin_access)
def admin_user_management(request):
    """Admin-only view for managing user activation status and primary roles."""
    available_roles = Group.objects.order_by('name')
    invalid_activation_form = None
    invalid_activation_user_id = None
    invalid_role_form = None
    invalid_role_user_id = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'activation':
            activation_form = UserActivationForm(request.POST)
            user_id_value = request.POST.get('user_id')
            invalid_activation_form = activation_form
            try:
                invalid_activation_user_id = int(user_id_value)
            except (TypeError, ValueError):
                invalid_activation_user_id = None

            if activation_form.is_valid():
                target_user = get_object_or_404(User, pk=activation_form.cleaned_data['user_id'])
                if target_user == request.user:
                    messages.error(request, 'You cannot change your own activation status.')
                elif target_user.is_superuser and not request.user.is_superuser:
                    messages.error(request, "Only superusers may change another superuser's status.")
                else:
                    desired_state = activation_form.cleaned_data['action'] == 'activate'
                    if target_user.is_active == desired_state:
                        status_label = 'active' if desired_state else 'inactive'
                        messages.info(request, f'{target_user.username} is already {status_label}.')
                    else:
                        previous_state = target_user.is_active
                        target_user.is_active = desired_state
                        target_user.save(update_fields=['is_active'])
                        status_label = 'activated' if desired_state else 'deactivated'
                        messages.success(request, f'{target_user.username} has been {status_label}.')
                        AuditLog.objects.create(
                            user=request.user,
                            action='update',
                            model_name='User',
                            object_id=str(target_user.pk),
                            object_repr=str(target_user),
                            changes={
                                'is_active': {
                                    'from': previous_state,
                                    'to': desired_state,
                                }
                            },
                            ip_address=request.META.get('REMOTE_ADDR'),
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        )
                    return redirect('admin_user_management')
            else:
                messages.error(request, 'Please correct the errors in the activation form.')
        elif form_type == 'role':
            role_form = UserRoleUpdateForm(request.POST, role_queryset=available_roles)
            user_id_value = request.POST.get('user_id')
            invalid_role_form = role_form
            try:
                invalid_role_user_id = int(user_id_value)
            except (TypeError, ValueError):
                invalid_role_user_id = None

            if role_form.is_valid():
                target_user = get_object_or_404(User, pk=role_form.cleaned_data['user_id'])
                if target_user == request.user:
                    messages.error(request, 'You cannot change your own role.')
                elif target_user.is_superuser and not request.user.is_superuser:
                    messages.error(request, "Only superusers may change another superuser's role.")
                else:
                    selected_role = role_form.cleaned_data['role']
                    previous_roles = list(target_user.groups.values_list('name', flat=True))
                    if selected_role and selected_role.name in previous_roles and len(previous_roles) == 1:
                        messages.info(request, f'{target_user.username} already has role {selected_role.name}.')
                    else:
                        target_user.groups.clear()
                        target_user.groups.add(selected_role)
                        messages.success(request, f'{target_user.username} role updated to {selected_role.name}.')
                        AuditLog.objects.create(
                            user=request.user,
                            action='update',
                            model_name='User',
                            object_id=str(target_user.pk),
                            object_repr=str(target_user),
                            changes={
                                'groups': {
                                    'from': previous_roles,
                                    'to': [selected_role.name],
                                }
                            },
                            ip_address=request.META.get('REMOTE_ADDR'),
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        )
                    return redirect('admin_user_management')
            else:
                messages.error(request, 'Please correct the errors in the role form.')
        else:
            messages.error(request, 'Unknown form submission.')
            return redirect('admin_user_management')

    users_queryset = User.objects.prefetch_related('groups').order_by('username')
    total_users = users_queryset.count()
    active_user_count = users_queryset.filter(is_active=True).count()
    inactive_user_count = total_users - active_user_count
    role_stats = Group.objects.order_by('name').annotate(user_count=Count('user'))

    if total_users:
        active_percentage = round((active_user_count / total_users) * 100)
        inactive_percentage = 100 - active_percentage
    else:
        active_percentage = 0
        inactive_percentage = 0

    user_rows = []
    for user_obj in users_queryset:
        primary_group = user_obj.groups.order_by('name').first()
        activation_action = 'deactivate' if user_obj.is_active else 'activate'

        activation_form = UserActivationForm(initial={
            'user_id': user_obj.pk,
            'action': activation_action,
        })

        role_form = UserRoleUpdateForm(
            initial={
                'user_id': user_obj.pk,
                'role': primary_group.pk if primary_group else None,
            },
            role_queryset=available_roles,
        )

        # Rehydrate invalid forms for the specific user row
        if invalid_activation_user_id == user_obj.pk and invalid_activation_form is not None:
            activation_form = invalid_activation_form
        if invalid_role_user_id == user_obj.pk and invalid_role_form is not None:
            role_form = invalid_role_form

        user_rows.append({
            'user': user_obj,
            'primary_group': primary_group,
            'activation_form': activation_form,
            'role_form': role_form,
            'activation_action': activation_action,
            'is_self': user_obj == request.user,
            'is_superuser': user_obj.is_superuser,
        })

    context = {
        'user_rows': user_rows,
        'available_roles': available_roles,
        'total_users': total_users,
        'active_user_count': active_user_count,
        'inactive_user_count': inactive_user_count,
        'active_percentage': active_percentage,
        'inactive_percentage': inactive_percentage,
        'role_stats': role_stats,
    }

    return render(request, 'core/admin_user_management.html', context)


@login_required
def admin_dashboard(request):
    """Admin dashboard with system overview and management tools"""
    if not (request.user.is_superuser or is_in_group(request.user, 'Admin')):
        return redirect(role_redirect(request.user))
    
    # System statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = total_users - active_users

    total_ledgers = LedgerUpload.objects.count()

    storage_bytes = 0
    for upload in LedgerUpload.objects.all():
        try:
            storage_bytes += upload.file.size
        except (FileNotFoundError, OSError, ValueError):
            continue
    storage_used_mb = storage_bytes / (1024 * 1024) if storage_bytes else 0

    total_transactions = Transaction.objects.count()
    high_risk_transactions = Transaction.objects.filter(risk_score__gt=70).count()
    high_risk_percentage = round((high_risk_transactions / total_transactions) * 100) if total_transactions else 0

    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'total_ledgers': total_ledgers,
        'storage_used': storage_used_mb,
        'risk_profiles': RiskProfile.objects.count(),
        'total_transactions': total_transactions,
        'high_risk_transactions': high_risk_transactions,
        'high_risk_percentage': high_risk_percentage,
    }

    # Ledger status summary
    status_label_map = dict(LedgerUpload.STATUS_CHOICES)
    ledger_status_counts = [
        {
            'status': entry['status'],
            'label': status_label_map.get(entry['status'], entry['status'].title()),
            'count': entry['count'],
            'percentage': round((entry['count'] / total_ledgers) * 100) if total_ledgers else 0,
        }
        for entry in LedgerUpload.objects.values('status').annotate(count=Count('id')).order_by('status')
    ]

    # Recent activity
    recent_activity = AuditLog.objects.select_related('user').order_by('-timestamp')[:5]

    # Recently active users
    recent_users = User.objects.filter(last_login__isnull=False).order_by('-last_login')[:5]

    # Recent uploads
    recent_uploads = LedgerUpload.objects.select_related(
        'uploaded_by', 'risk_profile'
    ).order_by('-uploaded_at')[:5]

    # Recent alerts
    recent_alerts = Alert.objects.select_related(
        'transaction', 'created_by', 'assigned_to'
    ).order_by('-created_at')[:5]

    # Risk profile effectiveness
    risk_profiles = RiskProfile.objects.annotate(
        usage_count=Count('ledgerupload'),
        avg_risk_score=Avg('ledgerupload__risk_score')
    ).order_by('-usage_count')[:5]

    return render(request, 'core/admin_dashboard.html', {
        'stats': stats,
        'recent_activity': recent_activity,
        'recent_users': recent_users,
        'recent_uploads': recent_uploads,
        'recent_alerts': recent_alerts,
        'risk_profiles': risk_profiles,
        'ledger_status_counts': ledger_status_counts,
    })


@login_required
def auditor_dashboard(request):
    """Auditor dashboard with risk analysis and investigation tools"""
    if not (request.user.is_superuser or is_in_group(request.user, 'Auditor') or is_in_group(request.user, 'Admin')):
        return redirect(role_redirect(request.user))

    now = timezone.now()
    thirty_days_ago = now - timezone.timedelta(days=30)

    transactions_last_30 = Transaction.objects.filter(date__gte=thirty_days_ago)

    total_transactions = transactions_last_30.count()
    high_risk_count = transactions_last_30.filter(risk_score__gt=70).count()
    average_risk_score = transactions_last_30.aggregate(avg=Avg('risk_score'))['avg'] or 0
    alert_count = Alert.objects.filter(created_at__gte=thirty_days_ago).count()

    stats = {
        'total_transactions': total_transactions,
        'high_risk_count': high_risk_count,
        'avg_risk_score': average_risk_score,
        'alert_count': alert_count,
    }

    ledger_totals = LedgerUpload.objects.aggregate(
        completed=Count('id', filter=Q(status='completed')),
        processing=Count('id', filter=Q(status='processing')),
        pending=Count('id', filter=Q(status='pending')),
        total=Count('id'),
    )
    ledger_stats = {
        'completed': ledger_totals.get('completed') or 0,
        'processing': ledger_totals.get('processing') or 0,
        'pending': ledger_totals.get('pending') or 0,
        'total': ledger_totals.get('total') or 0,
    }

    risk_distribution = [
        transactions_last_30.filter(risk_score__lte=30).count(),
        transactions_last_30.filter(risk_score__gt=30, risk_score__lte=70).count(),
        transactions_last_30.filter(risk_score__gt=70).count(),
    ]

    high_risk_transactions = Transaction.objects.filter(
        risk_score__gt=70
    ).select_related('ledger_upload').order_by('-date')[:10]

    recent_activity = AuditLog.objects.filter(
        model_name__in=['LedgerUpload', 'Transaction', 'Alert']
    ).select_related('user').order_by('-timestamp')[:5]

    avg_transaction_amount = transactions_last_30.aggregate(avg=Avg('amount'))['avg'] or 0
    repeated_descriptions = transactions_last_30.values('description').annotate(
        count=Count('id')
    ).filter(count__gt=1).count()
    distinct_ledgers = transactions_last_30.values('ledger_upload').distinct().count()

    risk_metrics = [
        {
            'label': 'Average Transaction Amount',
            'value': avg_transaction_amount,
            'format': 'currency',
        },
        {
            'label': 'Repeated Descriptions (30d)',
            'value': repeated_descriptions,
            'format': 'number',
        },
        {
            'label': 'Distinct Ledgers Reviewed (30d)',
            'value': distinct_ledgers,
            'format': 'number',
        },
        {
            'label': 'Alerts Created (30d)',
            'value': alert_count,
            'format': 'number',
        },
    ]

    avg_risk = stats['avg_risk_score']
    if avg_risk >= 70:
        risk_score_class = 'risk-high'
    elif avg_risk >= 40:
        risk_score_class = 'risk-medium'
    else:
        risk_score_class = 'risk-low'

    return render(request, 'core/auditor_dashboard.html', {
        'stats': stats,
        'ledger_stats': ledger_stats,
        'risk_distribution': risk_distribution,
        'high_risk_transactions': high_risk_transactions,
        'recent_activity': recent_activity,
        'risk_metrics': risk_metrics,
        'risk_score_class': risk_score_class,
        'time_window_start': thirty_days_ago,
        'time_window_end': now,
    })


@login_required
def finance_dashboard(request):
    """Finance dashboard with transaction monitoring and reporting"""
    if not (request.user.is_superuser or is_in_group(request.user, 'FinanceOfficer') or is_in_group(request.user, 'Admin')):
        return redirect(role_redirect(request.user))
    
    now = timezone.now()
    thirty_days_ago = now - timezone.timedelta(days=30)
    
    transactions = Transaction.objects.filter(date__gte=thirty_days_ago)
    transactions_for_finance = transactions.select_related('ledger_upload', 'reviewed_by')
    transaction_aggregates = transactions_for_finance.aggregate(
        total_amount=Sum('amount'),
        avg_transaction=Avg('amount'),
        risk_score_avg=Avg('risk_score'),
    )
    stats = {
        'total_amount': transaction_aggregates.get('total_amount') or 0,
        'transaction_count': transactions.count(),
        'avg_transaction': transaction_aggregates.get('avg_transaction') or 0,
        'risk_score_avg': transaction_aggregates.get('risk_score_avg') or 0,
    }
    
    recent_transactions = transactions_for_finance.order_by('-date')[:10]
    
    daily_trend_entries = list(
        transactions.values('date__date').annotate(
            total_amount=Sum('amount'),
            avg_risk=Avg('risk_score'),
            count=Count('id'),
        ).order_by('date__date')
    )
    max_count = max((entry['count'] for entry in daily_trend_entries), default=0)
    daily_trends = [
        {
            'date': entry['date__date'],
            'count': entry['count'],
            'total_amount': entry['total_amount'] or 0,
            'avg_risk': entry['avg_risk'] or 0,
            'progress_pct': int(round((entry['count'] / max_count) * 100)) if max_count else 0,
        }
        for entry in daily_trend_entries
    ]
    
    return render(request, 'core/finance_dashboard.html', {
        'stats': stats,
        'recent_transactions': recent_transactions,
        'daily_trends': daily_trends,
        'time_window_start': thirty_days_ago,
        'time_window_end': now,
    })


@login_required
def reviewer_dashboard(request):
    """Reviewer dashboard with alert management and case handling"""
    if not (request.user.is_superuser or is_in_group(request.user, 'Reviewer') or is_in_group(request.user, 'Admin')):
        return redirect(role_redirect(request.user))
    
    now = timezone.now()
    thirty_days_ago = now - timezone.timedelta(days=30)
    
    my_alerts = Alert.objects.filter(
        assigned_to=request.user,
        created_at__gte=thirty_days_ago,
    ).select_related('transaction', 'transaction__ledger_upload').order_by('-created_at')
    
    stats = {
        'risk_score': my_alerts.aggregate(avg_risk=Avg('transaction__risk_score'))['avg_risk'] or 0,
        'risk_score_class': 'risk-high' if my_alerts.filter(transaction__risk_score__gte=70).exists() else (
            'risk-medium' if my_alerts.filter(transaction__risk_score__gte=40).exists() else 'risk-low'
        ),
        'reviewed': my_alerts.filter(status='resolved').count(),
        'assigned': my_alerts.count(),
        'pending_review': my_alerts.filter(status='new').count(),
        'in_progress': my_alerts.filter(status='in_progress').count(),
        'avg_resolution_time': _format_duration(
            my_alerts.filter(resolved_at__isnull=False).aggregate(
                avg_duration=Avg(
                    ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField())
                )
            )['avg_duration']
        ),
    }
    stats['risk_score_class'] = _determine_risk_class(stats['risk_score'])
    
    high_risk_alerts = my_alerts.filter(transaction__risk_score__gte=70)[:10]
    recent_notes = my_alerts.exclude(description="").values(
        'title',
        'description',
        'created_at',
        'created_by__username'
    )[:5]
    status_counts = my_alerts.values('status').annotate(count=Count('id'))
    status_label_map = dict(Alert.STATUS_CHOICES)
    status_breakdown = [
        {
            'label': status_label_map.get(entry['status'], entry['status'].title()),
            'count': entry['count'],
            'percentage': int(round((entry['count'] / stats['assigned']) * 100)) if stats['assigned'] else 0,
        }
        for entry in status_counts
    ]
    
    return render(request, 'core/reviewer_dashboard.html', {
        'stats': stats,
        'high_risk_alerts': high_risk_alerts,
        'status_breakdown': status_breakdown,
        'recent_notes': [
            {
                'title': note['title'],
                'body': note['description'],
                'created_at': note['created_at'],
                'author_name': note['created_by__username'],
            }
            for note in recent_notes
        ],
        'time_window_start': thirty_days_ago,
        'time_window_end': now,
    })


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created successfully. Welcome, {user.username}!')
            return redirect(role_redirect(user))
    else:
        form = UserRegistrationForm()
    return render(request, 'core/register.html', {'form': form})


class RBACLoginView(LoginView):
    template_name = 'core/login.html'

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        return reverse(role_redirect(self.request.user))


def landing_page(request):
    if request.user.is_authenticated:
        return redirect(role_redirect(request.user))
    return render(request, 'core/landing_page.html')


def demo_landing(request):
    return render(request, 'core/demo_landing.html')


def guest_dashboard(request):
    # open to all; if logged in and not a guest, redirect to their role's dashboard
    if request.user.is_authenticated and not is_in_group(request.user, 'Guest'):
        return redirect(role_redirect(request.user))
    return render(request, 'core/guest_dashboard.html')


@login_required
@user_passes_test(can_upload_ledger)
def upload_ledger(request):
    """Handle ledger file uploads for authorized users and process with risk engine."""
    if request.method == 'POST':
        form = UploadLedgerForm(request.POST, request.FILES)
        if form.is_valid():
            ledger = form.save(commit=False)
            ledger.uploaded_by = request.user
            ledger.filename = request.FILES['file'].name
            ledger.status = 'processing'
            
            # Get selected risk profile if specified
            risk_profile_id = request.POST.get('risk_profile')
            if risk_profile_id:
                try:
                    ledger.risk_profile = RiskProfile.objects.get(id=risk_profile_id)
                except RiskProfile.DoesNotExist:
                    pass
            
            ledger.save()

            try:
                # Get the file path after model save
                file_path = os.path.join(settings.MEDIA_ROOT, str(ledger.file))
                
                # Process the file with our risk engine
                overall_risk, high_risk_count = process_ledger_file(file_path, ledger)
                
                # Success message with risk details
                messages.success(
                    request,
                    f'Ledger processed successfully. Overall risk score: {overall_risk:.2f}'
                )
                
                # If user is auditor/admin, show more details
                if is_in_group(request.user, 'Auditor') or is_in_group(request.user, 'Admin'):
                    high_risk_transactions = Transaction.objects.filter(
                        ledger_upload=ledger,
                        risk_score__gt=70
                    ).order_by('-risk_score')[:3]
                    
                    if high_risk_transactions:
                        risk_msg = "Top risky transactions:\n"
                        for tx in high_risk_transactions:
                            risk_msg += (
                                f"- {tx.description}: "
                                f"${tx.amount:,.2f} "
                                f"(Risk: {tx.risk_score:.1f})\n"
                            )
                        messages.info(request, risk_msg)
                    
                    # Show alert summary
                    alerts = Alert.objects.filter(
                        transaction__ledger_upload=ledger
                    ).count()
                    if alerts:
                        messages.info(
                            request,
                            f"{alerts} alert{'s' if alerts != 1 else ''} generated and assigned to reviewers."
                        )
                
            except Exception as e:
                ledger.status = 'error'
                ledger.error_message = str(e)
                ledger.save()
                messages.error(request, f'Error processing file: {str(e)}')
            
            return redirect('upload_ledger')
    else:
        form = UploadLedgerForm()
    
    # Get risk profiles for selection
    risk_profiles = RiskProfile.objects.filter(is_active=True).order_by('-created_at')
    
    # Get recent uploads with more details
    recent_uploads = LedgerUpload.objects.filter(
        uploaded_by=request.user
    ).select_related('risk_profile').annotate(
        alert_count=Count('transaction__alerts'),
        calculated_high_risk_count=Count(
            'transaction',
            filter=Q(transaction__risk_score__gt=70)
        )
    ).order_by('-uploaded_at')[:5]
    
    # Get statistics
    upload_count = LedgerUpload.objects.filter(uploaded_by=request.user).count()
    high_risk_count = Transaction.objects.filter(
        ledger_upload__uploaded_by=request.user,
        risk_score__gt=70
    ).count()
    
    return render(request, 'core/upload_ledger.html', {
        'form': form,
        'risk_profiles': risk_profiles,
        'recent_uploads': recent_uploads,
        'upload_count': upload_count,
        'high_risk_count': high_risk_count
    })
