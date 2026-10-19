"""Read-only financial integrity audit.

This command never writes: it only reads the ledger and prints findings so an
operator can decide what (if anything) to fix. Historical records are never
auto-corrected; a stale ``PAID`` row with a real balance is reported, not
repaired.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count

from frontend.models import AccountReceivable, Payment, quantize_money


class Command(BaseCommand):
    help = (
        'Read-only audit of payment/receivable integrity: stale statuses, '
        'overpayments, invalid amounts, cancelled-with-payments, sale '
        'mismatches and duplicate idempotency keys.'
    )

    def handle(self, *args, **options):
        self.findings = 0
        self.stdout.write('Financial integrity audit (read-only)')
        self.stdout.write('=' * 40)

        self._stale_paid()
        self._stale_open()
        self._invalid_amounts()
        self._overpayments()
        self._cancelled_with_payments()
        self._sale_mismatches()
        self._duplicate_keys()
        self._summary()

        self.stdout.write('')
        if self.findings:
            self.stdout.write(self.style.WARNING(
                f'{self.findings} finding(s) require operator review. '
                'No data was modified.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'No financial integrity issues detected. No data was modified.'
            ))

    def _finding(self, message):
        self.findings += 1
        self.stdout.write(self.style.WARNING(f'  ! {message}'))

    def _stale_paid(self):
        self.stdout.write('PAID receivables with an outstanding balance:')
        found = False
        for account in AccountReceivable.objects.filter(status='PAID'):
            balance = account.remaining_balance
            if balance > Decimal('0.00'):
                found = True
                self._finding(
                    f'{account.reference} (AR #{account.pk}, {account.person.name}) '
                    f'status=PAID but R$ {balance:.2f} outstanding'
                )
        if not found:
            self.stdout.write('  none')

    def _stale_open(self):
        self.stdout.write('Open receivables with no outstanding balance:')
        found = False
        for account in AccountReceivable.objects.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
        ):
            if account.remaining_balance <= Decimal('0.00'):
                found = True
                self._finding(
                    f'{account.reference} (AR #{account.pk}, {account.person.name}) '
                    f'status={account.status} but fully settled'
                )
        if not found:
            self.stdout.write('  none')

    def _invalid_amounts(self):
        self.stdout.write('Amounts below R$ 0.01 or with sub-cent precision:')
        found = False
        for account in AccountReceivable.objects.all():
            if account.original_amount < Decimal('0.01'):
                found = True
                self._finding(
                    f'{account.reference} (AR #{account.pk}) original_amount='
                    f'{account.original_amount}'
                )
            elif quantize_money(account.original_amount) != account.original_amount:
                found = True
                self._finding(
                    f'{account.reference} (AR #{account.pk}) sub-cent original_amount='
                    f'{account.original_amount}'
                )
        for payment in Payment.objects.all():
            if payment.amount < Decimal('0.01'):
                found = True
                self._finding(
                    f'Payment #{payment.pk} amount={payment.amount} below minimum'
                )
            elif quantize_money(payment.amount) != payment.amount:
                found = True
                self._finding(
                    f'Payment #{payment.pk} sub-cent amount={payment.amount}'
                )
        if not found:
            self.stdout.write('  none')

    def _overpayments(self):
        self.stdout.write('Receivables paid beyond their original amount:')
        found = False
        for account in AccountReceivable.objects.all():
            paid = account.amount_paid
            if paid > account.original_amount:
                found = True
                self._finding(
                    f'{account.reference} (AR #{account.pk}) original='
                    f'R$ {account.original_amount:.2f} paid=R$ {paid:.2f}'
                )
        if not found:
            self.stdout.write('  none')

    def _cancelled_with_payments(self):
        self.stdout.write(
            'Cancelled receivables carrying payments (may be a legitimate '
            'refund trail; verify manually):'
        )
        found = False
        for account in AccountReceivable.objects.filter(status='CANCELLED'):
            if account.payments.exists():
                found = True
                self._finding(
                    f'{account.reference} (AR #{account.pk}) cancelled but has '
                    f'{account.payments.count()} payment(s)'
                )
        if not found:
            self.stdout.write('  none')

    def _sale_mismatches(self):
        self.stdout.write('Receivables whose amount differs from their sale total:')
        found = False
        for account in AccountReceivable.objects.select_related('sale').filter(
            sale__isnull=False,
        ):
            if account.original_amount != account.sale.total:
                found = True
                self._finding(
                    f'{account.reference} (AR #{account.pk}) original='
                    f'R$ {account.original_amount:.2f} != sale total '
                    f'R$ {account.sale.total:.2f}'
                )
        if not found:
            self.stdout.write('  none')

    def _duplicate_keys(self):
        self.stdout.write('Duplicate payment idempotency keys:')
        duplicates = (
            Payment.objects.exclude(idempotency_key__isnull=True)
            .values('idempotency_key')
            .annotate(total=Count('id'))
            .filter(total__gt=1)
        )
        if duplicates:
            for row in duplicates:
                self._finding(
                    f'key {row["idempotency_key"]!r} used by {row["total"]} payments'
                )
        else:
            self.stdout.write('  none')

    def _summary(self):
        self.stdout.write('')
        self.stdout.write('Ledger summary:')
        self.stdout.write(
            f'  receivables: {AccountReceivable.objects.count()} '
            f'(cancelled: {AccountReceivable.objects.filter(status="CANCELLED").count()})'
        )
        self.stdout.write(f'  payments: {Payment.objects.count()}')
        total_paid = sum(
            (payment.amount for payment in Payment.objects.all()), Decimal('0.00'),
        )
        self.stdout.write(f'  total recorded payments: R$ {quantize_money(total_paid):.2f}')
        outstanding = Decimal('0.00')
        for account in AccountReceivable.objects.exclude(status='CANCELLED'):
            outstanding += account.remaining_balance
        self.stdout.write(
            f'  outstanding balance (non-cancelled): R$ {quantize_money(outstanding):.2f}'
        )
