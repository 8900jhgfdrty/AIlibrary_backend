import os
import django

# Configure Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LibraryManagementSystem.settings')
django.setup()

from api.models import User, Role, Permission

# Create a new user
user = User.objects.create(
    username="LYJ",
    password="123456",  # Note: Use hashed passwords in production
    is_super=False  # Ensure the user is not a superuser
)

# Create a new role
role = Role.objects.create(name="Standard User")

# Retrieve permissions
try:
    perm1 = Permission.objects.get(route="api/announcements/", method="GET")  # View announcements
    perm2 = Permission.objects.get(route="api/announcements/", method="POST")  # Create announcements
except Permission.DoesNotExist:
    print("Error: Required permissions are missing in the database.")
    exit()

# Assign permissions to the role
role.permissions.add(perm1, perm2)

# Assign the role to the user
user.roles.add(role)

# Verify assigned permissions
print("\nVerification of assigned permissions:")
if user.is_super:
    all_permissions = Permission.objects.all()
else:
    all_permissions = Permission.objects.filter(role__in=user.roles.all()).distinct()

print("User permissions:")
for perm in all_permissions:
    print(f"Permission: {perm.name}, Route: {perm.route}, Method: {perm.method}")
