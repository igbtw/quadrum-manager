from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from frontend import demo_data
from frontend.demo_data import DEMO_USER_PREFIX, DemoDataError


class Command(BaseCommand):
    help = (
        'Populate the database with a realistic, reversible demo dataset for '
        'local presentations (development only). Remove it again with '
        'clear_demo_data.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed', type=int, default=42,
            help='Random seed for reproducible data (default: 42).',
        )

    def handle(self, *args, **options):
        try:
            demo_data.require_enabled()
        except DemoDataError as exc:
            raise CommandError(str(exc))

        if demo_data.manifest_exists():
            raise CommandError(
                f'A demo dataset manifest already exists at {demo_data.manifest_path()}. '
                'Run `python manage.py clear_demo_data` first, then seed again.',
            )
        if User.objects.filter(username__startswith=DEMO_USER_PREFIX).exists():
            raise CommandError(
                f'Accounts with the {DEMO_USER_PREFIX!r} prefix exist without a manifest; '
                'refusing to create a duplicate dataset. Inspect and remove them manually first.',
            )

        try:
            manifest, counts = demo_data.seed_demo_dataset(options['seed'])
        except Exception as exc:
            raise CommandError(f'Seeding failed and was rolled back: {exc}') from exc

        out = self.stdout
        out.write(self.style.SUCCESS(f'Demo dataset created (seed={options["seed"]}).'))
        out.write(
            f'  users: {counts["users"]}   categories: {counts["categories"]}   '
            f'products: {counts["products"]}   people: {counts["people"]}',
        )
        out.write(
            f'  sales: {counts["sales_total"]} (completed {counts["sales_completed"]}, '
            f'pending {counts["sales_pending"]}, cancelled {counts["sales_cancelled"]})',
        )
        out.write(
            f'  sale items: {counts["sale_items"]}   stock movements: {counts["stock_movements"]}   '
            f'receivables: {counts["receivables"]}   payments: {counts["payments"]}',
        )
        out.write('')
        out.write(f'Demo login for the presentation (development credentials), password: {demo_data.DEMO_PASSWORD}')
        for username in manifest['demo_usernames']:
            out.write(f'  {username}')
        out.write('')
        out.write('Remove everything again with: python manage.py clear_demo_data')
