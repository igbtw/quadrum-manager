from django.core.management.base import BaseCommand, CommandError

from frontend import demo_data
from frontend.demo_data import DemoDataConflictError, DemoDataError


class Command(BaseCommand):
    help = (
        'Remove every record created by seed_demo_data. Preserves the root '
        'account, unrelated records, the schema, and migration history.'
    )

    def handle(self, *args, **options):
        try:
            demo_data.require_enabled()
            result = demo_data.clear_demo_dataset()
        except DemoDataConflictError as exc:
            bullets = '\n  - '.join(exc.conflicts)
            raise CommandError(
                'Cleanup aborted; nothing was deleted. Resolve the following '
                f'conflicts and run the command again:\n  - {bullets}',
            )
        except DemoDataError as exc:
            raise CommandError(str(exc))

        status = result['status']
        if status == 'absent':
            self.stdout.write('No demo dataset found (no manifest). Nothing to clear.')
        elif status == 'stale-manifest':
            self.stdout.write(
                'Removed a stale demo manifest; no tracked demo records remained in the database.',
            )
        else:
            self.stdout.write(self.style.SUCCESS('Demo dataset cleared.'))
            for label, count in sorted(result['removed'].items()):
                if count:
                    self.stdout.write(f'  {label}: {count}')
            self.stdout.write('The root account and all unrelated records were left untouched.')
