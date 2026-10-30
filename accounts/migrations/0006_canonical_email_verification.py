from django.db import migrations, models


def copy_verified_emails(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')
    EmailAddress = apps.get_model('account', 'EmailAddress')
    alias = schema_editor.connection.alias
    emails = EmailAddress.objects.using(alias)
    for profile in Profile.objects.using(alias).filter(email_verified=True).select_related('user').iterator():
        email = profile.user.email.strip().lower()
        if not email:
            continue
        if emails.filter(email__iexact=email, verified=True).exclude(user_id=profile.user_id).exists():
            raise RuntimeError('Verified email ownership conflict; resolve it before migrating. No accounts were merged.')
        address = emails.filter(user_id=profile.user_id, email__iexact=email).first()
        if address is None:
            emails.create(user_id=profile.user_id, email=email, verified=True,
                          primary=not emails.filter(user_id=profile.user_id, primary=True).exists())
        else:
            address.verified = True
            address.save(using=alias, update_fields=['verified'])


def restore_legacy_flags(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')
    EmailAddress = apps.get_model('account', 'EmailAddress')
    alias = schema_editor.connection.alias
    for profile in Profile.objects.using(alias).select_related('user').iterator():
        verified = EmailAddress.objects.using(alias).filter(
            user_id=profile.user_id, email__iexact=profile.user.email, verified=True).exists()
        Profile.objects.using(alias).filter(pk=profile.pk).update(email_verified=verified)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_unique_user_email'),
        ('account', '0009_emailaddress_unique_primary_email'),
    ]
    operations = [
        migrations.RunPython(copy_verified_emails, restore_legacy_flags),
        migrations.RemoveField(model_name='profile', name='email_verified'),
        migrations.AddField(model_name='profile', name='verification_sent_at', field=models.DateTimeField(blank=True, null=True)),
    ]
