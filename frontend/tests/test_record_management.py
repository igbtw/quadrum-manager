"""Record management tests: edit, safe delete, and archive for People and
Products.

Policy under test:

* ``frontend.manage_master_data`` (superuser or explicit permission) gates
  edit/delete; ``view_all_responsible_data`` and ``is_staff`` do **not**
  imply it.
* Deletes are POST-only, CSRF-protected, and refuse referenced records with
  a clear message instead of erasing history (sales, receivables, sale
  items, stock movements keep their relationships).
* Deactivating a record (``active=False``) through the edit form is the
  archive path; unreferenced records delete cleanly.
* Invalid edits re-render the modal with bound values and errors, and
  never corrupt stored data.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db.models import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from frontend.models import (
    AccountReceivable, Category, Person, Product, Sale, SaleItem,
    StockMovement,
)
from frontend.services import (
    ReferencedRecordError, delete_person, delete_product,
)


class RecordManagementTestBase(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user('rm-manager', password='test-pass-123')
        self.manager.user_permissions.add(Permission.objects.get(
            content_type__app_label='frontend',
            codename='manage_master_data',
        ))
        self.plain = User.objects.create_user('rm-plain', password='test-pass-123')
        self.staff = User.objects.create_user(
            'rm-staff', password='test-pass-123', is_staff=True,
        )
        self.viewer = User.objects.create_user('rm-viewer', password='test-pass-123')
        self.viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='frontend',
            codename='view_all_responsible_data',
        ))
        self.admin = User.objects.create_superuser('rm-admin', password='test-pass-123')

        self.category = Category.objects.create(name='Bebidas')
        self.clean_person = Person.objects.create(
            name='Pessoa Limpa', doc_id='CLEAN-1', person_type='STUDENT',
        )
        self.clean_product = Product.objects.create(
            name='Livre', code='LIVRE-1', category=self.category,
            price=Decimal('5.00'), stock_quantity=10,
        )

    def login(self, user):
        client = Client()
        client.force_login(user)
        return client

    def make_sale(self, customer=None, product=None, responsible=None, quantity=1):
        product = product or self.clean_product
        subtotal = product.price * quantity
        sale = Sale.objects.create(
            customer=customer, responsible=responsible, status='COMPLETED',
            payment_method='CASH', subtotal=subtotal, total=subtotal,
            completed_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale, product=product, quantity=quantity, unit_price=product.price,
        )
        return sale

    def make_receivable(self, person, sale=None, amount='10.00'):
        return AccountReceivable.objects.create(
            person=person, sale=sale, original_amount=Decimal(amount),
            due_date=timezone.localdate(), status='PENDING',
        )

    def make_movement(self, product):
        return StockMovement.objects.create(
            product=product, movement_type='ADJUSTMENT', quantity=3,
            reason='test',
        )


class ManageMasterDataPermissionTests(RecordManagementTestBase):
    def test_permission_is_declared_on_person(self):
        self.assertTrue(Permission.objects.filter(
            content_type__app_label='frontend',
            codename='manage_master_data',
        ).exists())

    def test_anonymous_is_sent_to_login(self):
        client = Client()
        edit = client.get(reverse('frontend:person_edit', args=[self.clean_person.pk]))
        delete = client.post(reverse('frontend:person_delete', args=[self.clean_person.pk]))
        self.assertEqual(edit.status_code, 302)
        self.assertIn('/login/', edit['Location'])
        self.assertEqual(delete.status_code, 302)
        self.assertIn('/login/', delete['Location'])
        self.assertTrue(Person.objects.filter(pk=self.clean_person.pk).exists())

    def test_plain_staff_and_view_all_users_are_forbidden(self):
        for user in (self.plain, self.staff, self.viewer):
            client = self.login(user)
            self.assertEqual(
                client.get(reverse('frontend:person_edit', args=[self.clean_person.pk])).status_code,
                403, msg=f'{user.username} must not edit people',
            )
            self.assertEqual(
                client.get(reverse('frontend:product_edit', args=[self.clean_product.pk])).status_code,
                403, msg=f'{user.username} must not edit products',
            )
            self.assertEqual(
                client.post(reverse('frontend:person_delete', args=[self.clean_person.pk])).status_code,
                403, msg=f'{user.username} must not delete people',
            )
        self.assertTrue(Person.objects.filter(pk=self.clean_person.pk).exists())

    def test_forbidden_delete_never_reaches_the_service(self):
        client = self.login(self.viewer)
        with patch('frontend.views.delete_person') as service:
            client.post(reverse('frontend:person_delete', args=[self.clean_person.pk]))
        service.assert_not_called()

    def test_manager_and_superuser_pass_the_gate(self):
        for user in (self.manager, self.admin):
            client = self.login(user)
            response = client.get(reverse('frontend:person_edit', args=[self.clean_person.pk]))
            self.assertEqual(response.status_code, 200, msg=user.username)


class EditRecordTests(RecordManagementTestBase):
    def test_edit_get_renders_bound_modal(self):
        client = self.login(self.manager)
        response = client.get(reverse('frontend:person_edit', args=[self.clean_person.pk]))
        html = response.content.decode()
        self.assertIn('id="person-edit-modal"', html)
        self.assertIn('value="Pessoa Limpa"', html)
        self.assertIn(reverse('frontend:person_edit', args=[self.clean_person.pk]), html)

    def test_create_and_edit_forms_do_not_duplicate_field_ids(self):
        client = self.login(self.manager)

        people_html = client.get(
            reverse('frontend:person_edit', args=[self.clean_person.pk]),
        ).content.decode()
        self.assertEqual(people_html.count('id="id_name"'), 1)
        self.assertEqual(people_html.count('id="id_edit-name"'), 1)
        self.assertEqual(people_html.count('for="id_name"'), 1)
        self.assertEqual(people_html.count('for="id_edit-name"'), 1)

        products_html = client.get(
            reverse('frontend:product_edit', args=[self.clean_product.pk]),
        ).content.decode()
        self.assertEqual(products_html.count('id="id_name"'), 1)
        self.assertEqual(products_html.count('id="id_edit-name"'), 1)
        self.assertEqual(products_html.count('for="id_name"'), 1)
        self.assertEqual(products_html.count('for="id_edit-name"'), 1)

    def test_edit_get_unknown_record_is_404(self):
        client = self.login(self.manager)
        self.assertEqual(
            client.get(reverse('frontend:person_edit', args=[99999])).status_code, 404,
        )
        self.assertEqual(
            client.get(reverse('frontend:product_edit', args=[99999])).status_code, 404,
        )

    def test_person_edit_updates_and_redirects(self):
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:person_edit', args=[self.clean_person.pk]),
            {'edit-name': 'Pessoa Renomeada', 'edit-doc_id': 'CLEAN-1',
             'edit-person_type': 'TEACHER', 'edit-email': 'p@example.com',
             'edit-phone': '555-0100', 'edit-active': 'on'},
            follow=True,
        )
        self.assertRedirects(response, reverse('frontend:people'))
        self.clean_person.refresh_from_db()
        self.assertEqual(self.clean_person.name, 'Pessoa Renomeada')
        self.assertEqual(self.clean_person.person_type, 'TEACHER')
        self.assertEqual(self.clean_person.email, 'p@example.com')
        self.assertContains(response, 'updated')
        self.assertContains(response, 'alert-success')

    def test_invalid_person_edit_preserves_values_and_data(self):
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:person_edit', args=[self.clean_person.pk]),
            {'edit-name': '', 'edit-doc_id': 'KEEP-99', 'edit-person_type': 'STUDENT',
             'edit-email': 'bad-email', 'edit-phone': '', 'edit-active': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="person-edit-modal"', html)
        self.assertIn('value="KEEP-99"', html)
        self.assertIn('class="errorlist"', html)
        self.clean_person.refresh_from_db()
        self.assertEqual(self.clean_person.name, 'Pessoa Limpa')

    def test_person_edit_can_deactivate_as_archive_path(self):
        client = self.login(self.manager)
        client.post(
            reverse('frontend:person_edit', args=[self.clean_person.pk]),
            {'edit-name': self.clean_person.name, 'edit-doc_id': self.clean_person.doc_id,
             'edit-person_type': self.clean_person.person_type, 'edit-email': '',
             'edit-phone': ''},
        )
        self.clean_person.refresh_from_db()
        self.assertFalse(self.clean_person.active)

        active_html = client.get(reverse('frontend:people')).content.decode()
        self.assertNotIn('<td>Pessoa Limpa</td>', active_html)
        inactive_html = client.get(
            reverse('frontend:people'), {'state': 'inactive'},
        ).content.decode()
        self.assertIn('<td>Pessoa Limpa</td>', inactive_html)

    def test_product_edit_updates_and_redirects(self):
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:product_edit', args=[self.clean_product.pk]),
            {'edit-name': 'Livre Editado', 'edit-code': 'LIVRE-1',
             'edit-category': self.category.pk, 'edit-price': '7.50',
             'edit-cost_price': '3.00', 'edit-stock_quantity': 12,
             'edit-minimum_stock': 2, 'edit-description': 'novo',
             'edit-active': 'on'},
            follow=True,
        )
        self.assertRedirects(response, reverse('frontend:products'))
        self.clean_product.refresh_from_db()
        self.assertEqual(self.clean_product.name, 'Livre Editado')
        self.assertEqual(self.clean_product.price, Decimal('7.50'))
        self.assertEqual(self.clean_product.stock_quantity, 12)
        self.assertContains(response, 'updated')

    def test_invalid_product_edit_preserves_values(self):
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:product_edit', args=[self.clean_product.pk]),
            {'edit-name': '', 'edit-code': 'KEEP-CODE',
             'edit-category': self.category.pk, 'edit-price': '7.50',
             'edit-cost_price': '3.00', 'edit-stock_quantity': 12,
             'edit-minimum_stock': 2, 'edit-description': '',
             'edit-active': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="product-edit-modal"', html)
        self.assertIn('value="KEEP-CODE"', html)
        self.clean_product.refresh_from_db()
        self.assertEqual(self.clean_product.name, 'Livre')

    def test_delete_endpoints_reject_get(self):
        client = self.login(self.manager)
        self.assertEqual(
            client.get(reverse('frontend:person_delete', args=[self.clean_person.pk])).status_code,
            405,
        )
        self.assertEqual(
            client.get(reverse('frontend:product_delete', args=[self.clean_product.pk])).status_code,
            405,
        )

    def test_csrf_is_enforced_on_delete(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        response = client.post(
            reverse('frontend:person_delete', args=[self.clean_person.pk]),
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Person.objects.filter(pk=self.clean_person.pk).exists())


class DeleteRecordTests(RecordManagementTestBase):
    def test_clean_person_deletes_and_reports_success(self):
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:person_delete', args=[self.clean_person.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse('frontend:people'))
        self.assertContains(response, 'deleted')
        self.assertContains(response, 'alert-success')
        self.assertFalse(Person.objects.filter(pk=self.clean_person.pk).exists())

    def test_clean_product_deletes(self):
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:product_delete', args=[self.clean_product.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse('frontend:products'))
        self.assertContains(response, 'deleted')
        self.assertFalse(Product.objects.filter(pk=self.clean_product.pk).exists())

    def test_person_referenced_by_sale_is_kept_with_explanation(self):
        sale = self.make_sale(customer=self.clean_person, product=self.clean_product)
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:person_delete', args=[self.clean_person.pk]),
            follow=True,
        )
        self.assertTrue(Person.objects.filter(pk=self.clean_person.pk).exists())
        sale.refresh_from_db()
        self.assertEqual(sale.customer_id, self.clean_person.pk)
        self.assertContains(response, 'Cannot delete')
        self.assertContains(response, '1 sale(s)')
        self.assertContains(response, 'alert-danger')

    def test_person_referenced_by_receivable_is_kept(self):
        receivable = self.make_receivable(self.clean_person)
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:person_delete', args=[self.clean_person.pk]),
            follow=True,
        )
        self.assertTrue(Person.objects.filter(pk=self.clean_person.pk).exists())
        self.assertTrue(AccountReceivable.objects.filter(pk=receivable.pk).exists())
        self.assertContains(response, 'Cannot delete')

    def test_product_referenced_by_sale_item_is_kept(self):
        sale = self.make_sale(customer=self.clean_person, product=self.clean_product)
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:product_delete', args=[self.clean_product.pk]),
            follow=True,
        )
        self.assertTrue(Product.objects.filter(pk=self.clean_product.pk).exists())
        self.assertTrue(SaleItem.objects.filter(sale=sale).exists())
        self.assertContains(response, 'Cannot delete')
        self.assertContains(response, '1 sale item(s)')

    def test_product_referenced_by_stock_movement_is_kept(self):
        movement = self.make_movement(self.clean_product)
        client = self.login(self.manager)
        response = client.post(
            reverse('frontend:product_delete', args=[self.clean_product.pk]),
            follow=True,
        )
        self.assertTrue(Product.objects.filter(pk=self.clean_product.pk).exists())
        self.assertTrue(StockMovement.objects.filter(pk=movement.pk).exists())
        self.assertContains(response, 'Cannot delete')
        self.assertContains(response, '1 stock movement(s)')

    def test_superuser_delete_works(self):
        client = self.login(self.admin)
        client.post(reverse('frontend:person_delete', args=[self.clean_person.pk]))
        self.assertFalse(Person.objects.filter(pk=self.clean_person.pk).exists())

    def test_stale_second_delete_is_a_clean_404(self):
        client = self.login(self.manager)
        url = reverse('frontend:person_delete', args=[self.clean_person.pk])
        self.assertEqual(client.post(url).status_code, 302)
        self.assertEqual(client.post(url).status_code, 404)

    def test_nonexistent_delete_is_404(self):
        client = self.login(self.manager)
        self.assertEqual(
            client.post(reverse('frontend:person_delete', args=[99999])).status_code, 404,
        )
        self.assertEqual(
            client.post(reverse('frontend:product_delete', args=[99999])).status_code, 404,
        )

    def test_protected_error_is_handled_gracefully(self):
        person_client = self.login(self.manager)
        with patch(
            'frontend.views.delete_person',
            side_effect=ProtectedError('refused', set()),
        ):
            response = person_client.post(
                reverse('frontend:person_delete', args=[self.clean_person.pk]),
                follow=True,
            )
        self.assertContains(response, 'Cannot delete')
        self.assertContains(response, 'alert-danger')
        self.assertTrue(Person.objects.filter(pk=self.clean_person.pk).exists())

        product_client = self.login(self.manager)
        with patch(
            'frontend.views.delete_product',
            side_effect=ProtectedError('refused', set()),
        ):
            response = product_client.post(
                reverse('frontend:product_delete', args=[self.clean_product.pk]),
                follow=True,
            )
        self.assertContains(response, 'Cannot delete')
        self.assertTrue(Product.objects.filter(pk=self.clean_product.pk).exists())


class DeleteServiceTests(RecordManagementTestBase):
    def test_service_deletes_clean_records(self):
        person_pk = self.clean_person.pk
        product_pk = self.clean_product.pk
        delete_person(self.clean_person)
        delete_product(self.clean_product)
        self.assertFalse(Person.objects.filter(pk=person_pk).exists())
        self.assertFalse(Product.objects.filter(pk=product_pk).exists())

    def test_service_reports_reference_counts(self):
        sale = self.make_sale(customer=self.clean_person, product=self.clean_product)
        self.make_receivable(self.clean_person, sale=sale)
        with self.assertRaises(ReferencedRecordError) as ctx:
            delete_person(self.clean_person)
        self.assertEqual(ctx.exception.references, {'sales': 1, 'receivables': 1})
        self.assertTrue(Person.objects.filter(pk=self.clean_person.pk).exists())

        with self.assertRaises(ReferencedRecordError) as ctx:
            delete_product(self.clean_product)
        self.assertEqual(ctx.exception.references, {'sale_items': 1, 'movements': 0})
        self.assertTrue(Product.objects.filter(pk=self.clean_product.pk).exists())


class ManagementAffordanceTests(RecordManagementTestBase):
    def test_manager_sees_edit_and_guarded_delete_controls(self):
        self.make_sale(customer=self.clean_person, product=self.clean_product)
        client = self.login(self.manager)

        people_html = client.get(reverse('frontend:people')).content.decode()
        self.assertIn(reverse('frontend:person_edit', args=[self.clean_person.pk]), people_html)
        self.assertIn('data-confirm-destructive', people_html)
        self.assertIn('data-confirm-blocked="true"', people_html)
        self.assertIn('1 sale(s)', people_html)

        products_html = client.get(reverse('frontend:products')).content.decode()
        self.assertIn(reverse('frontend:product_edit', args=[self.clean_product.pk]), products_html)
        self.assertIn('data-confirm-destructive', products_html)
        self.assertIn('data-confirm-blocked="true"', products_html)
        self.assertIn('1 sale item(s)', products_html)

    def test_clean_records_get_a_confirmable_delete_form(self):
        client = self.login(self.manager)
        html = client.get(reverse('frontend:people')).content.decode()
        self.assertIn(reverse('frontend:person_delete', args=[self.clean_person.pk]), html)
        self.assertIn('btn-danger-ghost', html)
        self.assertNotIn('data-confirm-blocked="true"', html)

    def test_non_manager_gets_no_management_controls(self):
        client = self.login(self.plain)
        people_html = client.get(reverse('frontend:people')).content.decode()
        self.assertNotIn('data-confirm-destructive', people_html)
        self.assertNotIn(reverse('frontend:person_edit', args=[self.clean_person.pk]), people_html)

        products_html = client.get(reverse('frontend:products')).content.decode()
        self.assertNotIn('data-confirm-destructive', products_html)
        self.assertNotIn(reverse('frontend:product_edit', args=[self.clean_product.pk]), products_html)
