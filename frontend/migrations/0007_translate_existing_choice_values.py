# Data migration to translate legacy Portuguese choice values to English
from django.db import migrations


def update_choice_values(apps, schema_editor):
    Person = apps.get_model('frontend', 'Person')
    Sale = apps.get_model('frontend', 'Sale')
    Payment = apps.get_model('frontend', 'Payment')
    AccountReceivable = apps.get_model('frontend', 'AccountReceivable')

    # Person types
    Person.objects.filter(person_type='ALUNO').update(person_type='STUDENT')
    Person.objects.filter(person_type='PROFESSOR').update(person_type='TEACHER')
    Person.objects.filter(person_type='FUNCIONARIO').update(person_type='STAFF')
    Person.objects.filter(person_type='VISITANTE').update(person_type='VISITOR')

    # Sale payment methods
    Sale.objects.filter(payment_method='DINHEIRO').update(payment_method='CASH')
    Sale.objects.filter(payment_method='DEBITO').update(payment_method='DEBIT')
    Sale.objects.filter(payment_method='CREDITO').update(payment_method='CREDIT')
    Sale.objects.filter(payment_method='A_PRAZO').update(payment_method='ON_ACCOUNT')

    # Account receivable statuses
    AccountReceivable.objects.filter(status='Cancelado').update(status='CANCELLED')

    # Payment methods
    Payment.objects.filter(method='DINHEIRO').update(method='CASH')
    Payment.objects.filter(method='DEBITO').update(method='DEBIT')
    Payment.objects.filter(method='CREDITO').update(method='CREDIT')
    Payment.objects.filter(method='TRANSFERENCIA').update(method='TRANSFER')


class Migration(migrations.Migration):
    dependencies = [
        ('frontend', '0006_alter_accountreceivable_status_alter_payment_method_and_more'),
    ]

    operations = [
        migrations.RunPython(update_choice_values),
    ]
