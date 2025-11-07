from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication Views
    path('login/', views.RBACLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='core/login.html', next_page='login'), name='logout'),
    path('register/', views.register, name='register'),
    
    # Password Reset Views
    path('password_reset/', 
        auth_views.PasswordResetView.as_view(template_name='core/password_reset.html'),
        name='password_reset'),
    path('password_reset/done/', 
        auth_views.PasswordResetDoneView.as_view(template_name='core/password_reset_done.html'),
        name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(template_name='core/password_reset_confirm.html'),
        name='password_reset_confirm'),
    path('reset/done/', 
        auth_views.PasswordResetCompleteView.as_view(template_name='core/password_reset_complete.html'),
        name='password_reset_complete'),
    
    # Password Change Views
    path('password_change/', 
        auth_views.PasswordChangeView.as_view(template_name='core/password_change.html'),
        name='password_change'),
    path('password_change/done/', 
        auth_views.PasswordChangeDoneView.as_view(template_name='core/password_change_done.html'),
        name='password_change_done'),
    path('upload/', views.upload_ledger, name='upload_ledger'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.admin_user_management, name='admin_user_management'),
    path('auditor_dashboard/', views.auditor_dashboard, name='auditor_dashboard'),
    path('finance_dashboard/', views.finance_dashboard, name='finance_dashboard'),
    path('reviewer_dashboard/', views.reviewer_dashboard, name='reviewer_dashboard'),
    path('guest_dashboard/', views.guest_dashboard, name='guest_dashboard'),
    path('demo/', views.demo_landing, name='demo'),
]
