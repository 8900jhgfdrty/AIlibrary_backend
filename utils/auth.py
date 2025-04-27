from django.urls import resolve
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from django.conf import settings
import jwt
from rest_framework.exceptions import AuthenticationFailed
from api.models import WhitelistUrl, User as UserModel, Role
from django.core.cache import cache
import logging

logger = logging.getLogger('auth')

class User(object):
    def __init__(self, id, username, exp, is_super=False, user_type='0', roles=None, **kwargs):
        self.id = id
        self.username = username
        self.exp = exp
        self.is_superuser = is_super  # Add is_superuser attribute, corresponding to is_super
        self.is_super = is_super      # Ensure is_super is also set
        self.user_type = user_type    # Add user_type attribute
        self.roles = roles or []      # Role list
        
        # Save other possible fields
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self):
        return f"User(id={self.id}, username={self.username}, is_superuser={self.is_superuser}, user_type={self.user_type})"

    def has_role(self, role_name):
        """Check if user has specified role"""
        return role_name in self.roles

    @property
    def is_reader(self):
        """Check if user is a reader"""
        return str(self.user_type) == '0' or self.user_type == 0 or 'reader' in self.roles

    @property
    def is_librarian(self):
        """Check if user is a librarian"""
        return str(self.user_type) == '1' or self.user_type == 1 or 'librarian' in self.roles

    @property
    def is_admin(self):
        """Check if user is a system administrator"""
        return str(self.user_type) == '2' or self.user_type == 2 or self.is_superuser or self.is_super or 'system_admin' in self.roles
        
    @property
    def is_authenticated(self):
        """
        Always returns True. Indicates this is an authenticated user.
        This is required by Django authentication system.
        """
        return True
        
    @property
    def is_anonymous(self):
        """
        Always returns False. Indicates this is not an anonymous user.
        This is required by Django authentication system.
        """
        return False

    def clear_permissions_cache(self):
        """Clear user permissions cache"""
        cache_key = f"user_permissions_{self.id}"
        cache.delete(cache_key)


class RbacAuthentication(BaseAuthentication):
    def authenticate(self, request):
        """Authentication processing logic"""
        # 1. Get current request URL name
        url_name = resolve(request.path_info).url_name
        # 2. Generate complete URL name based on request, including app name and URL name
        full_url_name = f"{request.resolver_match.app_names[0]}:{url_name}" if request.resolver_match.app_names else url_name

        # 3. Check if current URL is in whitelist
        if WhitelistUrl.objects.filter(url_pattern=full_url_name).exists():
            return None  # Allow unauthenticated access

        # Handle OPTIONS request preflight
        if request.method == 'OPTIONS':
            return None

        # 4. Get jwt token from request header
        auth_header = get_authorization_header(request).split()
        # Check if Authorization header exists and starts with Bearer
        if not auth_header or auth_header[0].lower() != b'bearer':
            raise AuthenticationFailed("Authentication failed: Missing or incorrect authentication information")

        try:
            # Get token and decode
            jwt_token = auth_header[1].decode('utf-8')
        except IndexError:
            raise AuthenticationFailed("Authentication failed: Invalid authentication header")

        if not jwt_token:
            raise AuthenticationFailed("Authentication failed: Token not provided")

        # 5. Verify jwt token validity
        try:
            verified_payload = jwt.decode(jwt_token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Authentication failed: Token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Authentication failed: Invalid token")

        # 6. Get user role information from database
        user_id = verified_payload.get('id')
        roles = []
        
        try:
            # Get user role information
            user_obj = UserModel.objects.get(id=user_id)
            # Use correct reverse lookup relationship
            roles = list(user_obj.roles.all().values_list('name', flat=True))
            
            # Update role information and user_type in payload
            verified_payload['roles'] = roles
            verified_payload['user_type'] = user_obj.user_type
            verified_payload['is_super'] = user_obj.is_super
            
        except UserModel.DoesNotExist:
            logger.warning(f"User {user_id} does not exist in database but has valid token")
        except Exception as e:
            logger.error(f"Error getting user roles: {str(e)}")

        # Create user object
        user = User(**verified_payload)
        
        # 7. Return (request.user, request.auth)
        return user, jwt_token

    def authenticate_header(self, request):
        return 'Bearer'
