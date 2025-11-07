from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group
from django.core.validators import FileExtensionValidator
from .models import LedgerUpload, RiskProfile, Alert, Transaction


class UserRegistrationForm(UserCreationForm):
    """Form for user registration with role selection"""
    email = forms.EmailField(required=True)
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select your role in the organization"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        selected_role = self.cleaned_data.get('role')
        if commit:
            user.save()
            if selected_role:
                user.groups.add(selected_role)
        return user


class UploadLedgerForm(forms.ModelForm):
    """Form for uploading ledger files"""
    risk_profile = forms.ModelChoiceField(
        queryset=RiskProfile.objects.filter(is_active=True),
        required=False,
        empty_label="Default Risk Profile",
        help_text="Select a risk profile for analysis"
    )
    
    class Meta:
        model = LedgerUpload
        fields = ['file', 'risk_profile']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv,.xlsx'
            })
        }
        
    def clean_file(self):
        file = self.cleaned_data['file']
        if file.size > 10 * 1024 * 1024:  # 10MB limit
            raise forms.ValidationError('File size must be under 10MB')
        return file


class RiskProfileForm(forms.ModelForm):
    """Form for creating and editing risk profiles"""
    class Meta:
        model = RiskProfile
        fields = [
            'name', 'description', 'industry',
            'amount_threshold', 'frequency_threshold',
            'time_window_hours', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'industry': forms.TextInput(attrs={'class': 'form-control'}),
            'amount_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'frequency_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'time_window_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class AlertUpdateForm(forms.ModelForm):
    """Form for updating alert status and assignment"""
    class Meta:
        model = Alert
        fields = ['status', 'assigned_to']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'})
        }


class TransactionReviewForm(forms.ModelForm):
    """Form for reviewing transactions"""
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )
    
    class Meta:
        model = Transaction
        fields = ['status', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'})
        }


class DateRangeFilterForm(forms.Form):
    """Form for filtering by date range"""
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    risk_level = forms.ChoiceField(
        choices=[
            ('', 'All Risk Levels'),
            ('low', 'Low Risk (0-30)'),
            ('medium', 'Medium Risk (31-70)'),
            ('high', 'High Risk (71-100)')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Transaction.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class UserActivationForm(forms.Form):
    """Form for activating or deactivating a user account."""
    user_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.ChoiceField(
        choices=[('activate', 'Activate'), ('deactivate', 'Deactivate')],
        widget=forms.HiddenInput()
    )
    form_type = forms.CharField(
        widget=forms.HiddenInput(),
        initial='activation'
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        form_type = cleaned_data.get('form_type')
        if action not in {'activate', 'deactivate'}:
            raise forms.ValidationError('Invalid action requested.')
        if form_type != 'activation':
            raise forms.ValidationError('Invalid activation form submission.')
        return cleaned_data


class UserRoleUpdateForm(forms.Form):
    """Form for updating a user's primary role."""
    user_id = forms.IntegerField(widget=forms.HiddenInput())
    role = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    form_type = forms.CharField(
        widget=forms.HiddenInput(),
        initial='role'
    )

    def __init__(self, *args, role_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if role_queryset is not None:
            self.fields['role'].queryset = role_queryset
        self.fields['form_type'].initial = 'role'
