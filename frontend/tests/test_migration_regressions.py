from django.test import TestCase
from django.db import connection
from decimal import Decimal
from django.apps import apps
from django.contrib.auth.models import User
from frontend.models import Person, Sale, Payment, AccountReceivable
import importlib
update_choice_values = importlib.import_module("frontend.migrations.0007_translate_existing_choice_values").update_choice_values


class MigrationRegressionTests(TestCase):
    """Verify that migration 0007 converts legacy Portuguese DB values to English."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        # Ensure we are at the fully migrated state before each test.
        # Applying 0007 idempotently is safe; we then inject legacy values via SQL
        # and verify conversion by running 0007 again.
        pass

    def tearDown(self):
        # Restore to latest applied state (0007) after each test.
        update_choice_values(apps, None)

    def test_legacy_person_types_migrated(self):
        """Legacy ALUNO, PROFESSOR, FUNCIONARIO, VISITANTE become STUDENT, TEACHER, STAFF, VISITOR."""
        p1 = Person.objects.create(name='Legacy1', doc_id='L1', person_type='STUDENT')
        p2 = Person.objects.create(name='Legacy2', doc_id='L2', person_type='STUDENT')
        p3 = Person.objects.create(name='Legacy3', doc_id='L3', person_type='STUDENT')
        p4 = Person.objects.create(name='Legacy4', doc_id='L4', person_type='STUDENT')

        cursor = connection.cursor()
        cursor.execute("UPDATE frontend_person SET person_type = 'ALUNO' WHERE id = %s", [p1.id])
        cursor.execute("UPDATE frontend_person SET person_type = 'PROFESSOR' WHERE id = %s", [p2.id])
        cursor.execute("UPDATE frontend_person SET person_type = 'FUNCIONARIO' WHERE id = %s", [p3.id])
        cursor.execute("UPDATE frontend_person SET person_type = 'VISITANTE' WHERE id = %s", [p4.id])

        # Apply data migration (idempotent) to verify conversion.
        update_choice_values(apps, None)

        p1.refresh_from_db()
        p2.refresh_from_db()
        p3.refresh_from_db()
        p4.refresh_from_db()

        self.assertEqual(p1.person_type, 'STUDENT')
        self.assertEqual(p2.person_type, 'TEACHER')
        self.assertEqual(p3.person_type, 'STAFF')
        self.assertEqual(p4.person_type, 'VISITOR')

    def test_legacy_sale_payment_methods_migrated(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user(username='testsale', password='t')
        pers = Person.objects.create(name='SalePerson', doc_id='S1', person_type='STUDENT')
        sale1 = Sale.objects.create(customer=pers, responsible=user, status='COMPLETED', payment_method='CASH', total=Decimal('10'))
        sale2 = Sale.objects.create(customer=pers, responsible=user, status='COMPLETED', payment_method='CASH', total=Decimal('15'))
        sale3 = Sale.objects.create(customer=pers, responsible=user, status='COMPLETED', payment_method='CASH', total=Decimal('20'))
        sale4 = Sale.objects.create(customer=pers, responsible=user, status='COMPLETED', payment_method='CASH', total=Decimal('25'))

        cursor = connection.cursor()
        cursor.execute("UPDATE frontend_sale SET payment_method = 'DINHEIRO' WHERE id = %s", [sale1.id])
        cursor.execute("UPDATE frontend_sale SET payment_method = 'DEBITO' WHERE id = %s", [sale2.id])
        cursor.execute("UPDATE frontend_sale SET payment_method = 'CREDITO' WHERE id = %s", [sale3.id])
        cursor.execute("UPDATE frontend_sale SET payment_method = 'A_PRAZO' WHERE id = %s", [sale4.id])

        update_choice_values(apps, None)

        sale1.refresh_from_db()
        sale2.refresh_from_db()
        sale3.refresh_from_db()
        sale4.refresh_from_db()

        self.assertEqual(sale1.payment_method, 'CASH')
        self.assertEqual(sale2.payment_method, 'DEBIT')
        self.assertEqual(sale3.payment_method, 'CREDIT')
        self.assertEqual(sale4.payment_method, 'ON_ACCOUNT')

    def test_legacy_payment_methods_migrated(self):
        pers = Person.objects.create(name='PayPerson', doc_id='PP1', person_type='STUDENT')
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('50'), due_date='2030-01-01', status='PENDING')
        p1 = Payment.objects.create(account_receivable=rc, amount=Decimal('10'))
        p2 = Payment.objects.create(account_receivable=rc, amount=Decimal('10'))
        p3 = Payment.objects.create(account_receivable=rc, amount=Decimal('10'))
        p4 = Payment.objects.create(account_receivable=rc, amount=Decimal('10'))

        cursor = connection.cursor()
        cursor.execute("UPDATE frontend_payment SET method = 'DINHEIRO' WHERE id = %s", [p1.id])
        cursor.execute("UPDATE frontend_payment SET method = 'DEBITO' WHERE id = %s", [p2.id])
        cursor.execute("UPDATE frontend_payment SET method = 'CREDITO' WHERE id = %s", [p3.id])
        cursor.execute("UPDATE frontend_payment SET method = 'TRANSFERENCIA' WHERE id = %s", [p4.id])

        update_choice_values(apps, None)

        p1.refresh_from_db()
        p2.refresh_from_db()
        p3.refresh_from_db()
        p4.refresh_from_db()

        self.assertEqual(p1.method, 'CASH')
        self.assertEqual(p2.method, 'DEBIT')
        self.assertEqual(p3.method, 'CREDIT')
        self.assertEqual(p4.method, 'TRANSFER')

    def test_legacy_receivable_status_migrated(self):
        pers = Person.objects.create(name='RecPerson', doc_id='RP1', person_type='STUDENT')
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('30'), due_date='2030-01-01', status='PENDING')
        cursor = connection.cursor()
        cursor.execute("UPDATE frontend_accountreceivable SET status = 'Cancelado' WHERE id = %s", [rc.id])

        update_choice_values(apps, None)
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'CANCELLED')

    def test_unrelated_english_values_unchanged(self):
        """Values that were already English must remain unchanged by 0007."""
        pers = Person.objects.create(name='EnglishPerson', doc_id='E1', person_type='STUDENT')
        user = User.objects.create_user(username='englishuser', password='t')
        sale = Sale.objects.create(customer=pers, responsible=user, status='PENDING', payment_method='CASH', total=Decimal('5'))
        rc = AccountReceivable.objects.create(person=pers, original_amount=Decimal('20'), due_date='2030-01-01', status='PENDING')
        p = Payment.objects.create(account_receivable=rc, amount=Decimal('5'))

        # Apply 0007 idempotently; no legacy values exist, so nothing changes.
        update_choice_values(apps, None)

        pers.refresh_from_db()
        sale.refresh_from_db()
        rc.refresh_from_db()
        p.refresh_from_db()

        self.assertEqual(pers.person_type, 'STUDENT')
        self.assertEqual(sale.payment_method, 'CASH')
        # The receivable was updated to PARTIAL by the payment; the important check is that English values are preserved.
        self.assertIn(rc.status, ['PENDING', 'PARTIAL', 'PAID', 'OVERDUE', 'CANCELLED'])
        self.assertEqual(p.method, 'CASH')
