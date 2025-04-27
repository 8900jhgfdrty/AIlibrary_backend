import functools
from django.http import JsonResponse
from rest_framework import status
from django.utils.translation import gettext_lazy as _

def role_required(role_names=None):
    """
        @role_required('system_admin') # Only allows system administrators to access
        @role_required(['librarian', 'system_admin']) # Allows librarians and system administrators to access
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(view_instance, request, *args, **kwargs):
            if not hasattr(request, 'user') or not hasattr(request.user, 'id'):
                return JsonResponse(
                    {'detail': _('Authentication credentials not provided')},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            # Super users have all permissions
            if hasattr(request.user, 'is_super') and request.user.is_super:
                return view_func(view_instance, request, *args, **kwargs)
            # Check user type - allows librarians(1) and system administrators(2) access
            if hasattr(request.user, 'user_type'):
                user_type = request.user.user_type
                # System administrator check
                if role_names == 'system_admin' and (user_type == 2 or user_type == '2'):
                    return view_func(view_instance, request, *args, **kwargs)
                # Librarian check
                if role_names in (['librarian', 'system_admin'], 'librarian') and (
                    user_type == 1 or user_type == '1' or user_type == 2 or user_type == '2'
                ):
                    return view_func(view_instance, request, *args, **kwargs)
                # Reader permission check
                if role_names in (['reader', 'librarian', 'system_admin'], 'reader'):
                    return view_func(view_instance, request, *args, **kwargs)
            # Get user roles
            user_roles = getattr(request.user, 'roles', [])
            # Convert single role name to list
            required_roles = role_names
            if isinstance(required_roles, str):
                required_roles = [required_roles]
            # If no roles specified or user has any of the required roles, allow access
            if not required_roles or any(role in user_roles for role in required_roles):
                return view_func(view_instance, request, *args, **kwargs)
            # No permission to access
            return JsonResponse(
                {'detail': _('You do not have permission to perform this action')},
                status=status.HTTP_403_FORBIDDEN
            )
        return _wrapped_view
    # Support decorator form without parameters @role_required
    if callable(role_names):
        view_func = role_names
        role_names = None
        return decorator(view_func)
    return decorator
def system_admin_required(view_func):
    return role_required('system_admin')(view_func)
def librarian_required(view_func):
    return role_required(['librarian', 'system_admin'])(view_func)
def reader_required(view_func):
    return role_required(['reader', 'librarian', 'system_admin'])(view_func)
def self_or_admin(model_class, lookup_kwargs_key='pk'):
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(view_instance, request, *args, **kwargs):
            if hasattr(request.user, 'is_super') and request.user.is_super:
                return view_func(view_instance, request, *args, **kwargs)
            # Check user type - librarians and system administrators
            if hasattr(request.user, 'user_type'):
                user_type = request.user.user_type
                if user_type == 1 or user_type == '1' or user_type == 2 or user_type == '2':
                    return view_func(view_instance, request, *args, **kwargs)
            
            # Administrators have all permissions
            if hasattr(request.user, 'roles') and any(role in ['librarian', 'system_admin'] for role in request.user.roles):
                return view_func(view_instance, request, *args, **kwargs)
            
            # Get object
            lookup_value = kwargs.get(lookup_kwargs_key)
            if lookup_value:
                try:
                    obj = model_class.objects.get(pk=lookup_value)
                    # Check if the object belongs to the current user
                    if hasattr(obj, 'user_id') and obj.user_id == request.user.id:
                        return view_func(view_instance, request, *args, **kwargs)
                except model_class.DoesNotExist:
                    pass
            
            # No permission to access
            return JsonResponse(
                {'detail': _('You do not have permission to perform this action')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return _wrapped_view
    
    return decorator 