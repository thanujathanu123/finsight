"""Custom template filters for formatting metric values consistently."""

from django import template

register = template.Library()


@register.filter(name="format_metric")
def format_metric(value, fmt="number"):
    """Format metrics as currency, percentage, or plain numbers."""
    if value is None:
        return "—"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if fmt == "currency":
        return f"${numeric_value:,.2f}"
    if fmt == "percentage":
        return f"{numeric_value:.0f}%"

    # Default to plain number with thousands separator
    if numeric_value.is_integer():
        return f"{int(numeric_value):,}"
    return f"{numeric_value:,.2f}"