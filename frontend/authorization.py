"""Responsible-based data isolation.

Policy
======
Every sale records the user who created it in ``Sale.responsible``. Records
reachable from a sale (its items, the receivable generated for on-account
checkout, and the payments registered against that receivable) belong to the
sale's responsible user.

* Users with **global access** -- superusers, or users explicitly granted the
  ``frontend.view_all_responsible_data`` permission (directly, via a group,
  or through any other permission backend) -- see every record.
* Ordinary authenticated users see only records attributable to them.
* Records with no ownership path (a receivable whose ``sale`` is ``NULL``)
  are visible only with global access.

``is_staff`` deliberately does **not** grant global access: staff status is
an admin-site concept, not business-data authorization.

Record management
=================
Editing and deleting shared master data (people, products, categories) is a
separate capability from seeing every responsible's operational data:

* Users with **management access** -- superusers, or users explicitly granted
  the ``frontend.manage_master_data`` permission -- may edit and delete
  master-data records. Grant it through the Django admin (user or group
  permissions) or ``user.user_permissions.add(...)``.
* ``frontend.view_all_responsible_data`` does **not** imply management, and
  ``frontend.manage_master_data`` does not widen operational-data visibility.

Master data is shared company-wide: management is never scoped per user.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import AccountReceivable, Payment, Sale, SaleItem

VIEW_ALL_PERMISSION = 'frontend.view_all_responsible_data'
MANAGE_MASTER_DATA_PERMISSION = 'frontend.manage_master_data'


def has_global_access(user) -> bool:
    """True when ``user`` may see every responsible's records."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(VIEW_ALL_PERMISSION)


def can_manage_master_data(user) -> bool:
    """True when ``user`` may edit or delete master-data records."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(MANAGE_MASTER_DATA_PERMISSION)


def management_required(view):
    """Require login plus master-data management access (403 otherwise).

    Applied at the view layer so management scope is enforced even when a
    request bypasses the interface and posts directly to the URL.
    """
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not can_manage_master_data(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def scoped_sales(user):
    """Sales visible to ``user``."""
    qs = Sale.objects.all()
    if has_global_access(user):
        return qs
    return qs.filter(responsible=user)


def scoped_sale_items(user):
    """Sale items whose owning sale is visible to ``user``."""
    qs = SaleItem.objects.all()
    if has_global_access(user):
        return qs
    return qs.filter(sale__responsible=user)


def scoped_receivables(user):
    """Receivables reachable from a sale owned by ``user``.

    Sale-less receivables have no ownership path and stay global-only.
    """
    qs = AccountReceivable.objects.all()
    if has_global_access(user):
        return qs
    return qs.filter(sale__responsible=user)


def scoped_payments(user):
    """Payments whose receivable is reachable from a sale owned by ``user``."""
    qs = Payment.objects.all()
    if has_global_access(user):
        return qs
    return qs.filter(account_receivable__sale__responsible=user)
