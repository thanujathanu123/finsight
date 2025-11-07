from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_roles(sender, **kwargs):
    """Ensure default roles exist after migrations."""
    roles = ["Admin", "Auditor", "FinanceOfficer", "Reviewer", "Guest"]
    for role in roles:
        Group.objects.get_or_create(name=role)
