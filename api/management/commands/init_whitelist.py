from django.core.management.base import BaseCommand
from api.models import WhitelistUrl


class Command(BaseCommand):
    help = "Initialize API whitelist URLs"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to initialize whitelist URLs...'))

        # Define whitelist URL list (url_pattern, description)
        whitelist_urls = [
            ('login', 'User Login API'),
            ('api:login', 'User Login API (with namespace)'),
            ('swagger-ui', 'Swagger UI Documentation'),
            ('swagger-json', 'Swagger JSON Documentation'),
            ('redoc', 'ReDoc API Documentation'),
            ('static-schema', 'Static API Schema'),
            # Public APIs below
            ('book-list', 'Book List (GET)'),
            ('book-detail', 'Book Detail (GET)'),
            ('announcement-list', 'Announcement List (GET)'),
            ('announcement-detail', 'Announcement Detail (GET)'),
            ('category-list', 'Category List (GET)'),
            ('category-detail', 'Category Detail (GET)'),
            ('author-list', 'Author List (GET)'),
            ('author-detail', 'Author Detail (GET)'),
        ]

        # Clear existing whitelist
        WhitelistUrl.objects.all().delete()

        # Create new whitelist
        for url_pattern, description in whitelist_urls:
            WhitelistUrl.objects.create(
                url_pattern=url_pattern,
                description=description
            )

        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(whitelist_urls)} whitelist URL records')) 