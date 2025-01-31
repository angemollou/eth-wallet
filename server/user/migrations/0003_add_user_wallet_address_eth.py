# Generated by Django 4.2.2 on 2024-06-22 09:00

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_remove_user_username_user_first_name_user_last_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='wallet_address_eth',
            field=models.CharField(blank=True, max_length=42, validators=[django.core.validators.RegexValidator('^0[xX][0-9a-fA-F]{40}$', 'The field must be a 42-character hexadecimal address')], verbose_name='Ethereum wallet address'),
        ),
    ]
