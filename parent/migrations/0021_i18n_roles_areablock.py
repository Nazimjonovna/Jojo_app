# Hand-written migration — admin SSH ga kirib `makemigrations` ishlata olmadik,
# lekin barcha o'zgarishlar shu yerda yig'ilgan: AdminRole + User.admin_role,
# AreaBlockRule (premium hudud bloklash), va ko'p tilli kontent maydonlari.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parent', '0020_notificationrule_notificationrulelog'),
    ]

    operations = [
        # ============================================================
        # AdminRole (xodimga rol berish uchun)
        # ============================================================
        migrations.CreateModel(
            name='AdminRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True, default='')),
                ('permissions', models.JSONField(blank=True, default=list)),
                ('is_system', models.BooleanField(default=False, help_text="Tizim rollari — o'chirib bo'lmaydi (masalan: superadmin)")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Admin Role',
                'verbose_name_plural': 'Admin Roles',
                'ordering': ['name'],
            },
        ),

        # User.admin_role
        migrations.AddField(
            model_name='user',
            name='admin_role',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users',
                to='parent.adminrole',
            ),
        ),

        # ============================================================
        # AreaBlockRule (Premium hudud bloklash)
        # ============================================================
        migrations.CreateModel(
            name='AreaBlockRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=150)),
                ('trigger', models.CharField(choices=[('enter', 'Hududga kirganda'), ('exit', 'Hududdan chiqqanda')], default='enter', max_length=10)),
                ('blocked_packages', models.JSONField(blank=True, default=list)),
                ('block_all_apps', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('active_from', models.TimeField(blank=True, null=True)),
                ('active_to', models.TimeField(blank=True, null=True)),
                ('last_triggered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('child', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='child_area_block_rules', to='parent.user')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='area_block_rules', to='parent.user')),
                ('saved_location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='area_block_rules', to='parent.savedlocation')),
            ],
            options={
                'verbose_name': 'Hudud bloklash qoidasi',
                'verbose_name_plural': 'Hudud bloklash qoidalari',
                'ordering': ['-created_at'],
            },
        ),

        # ============================================================
        # Multilingual content (ru/en variantlari)
        # ============================================================
        migrations.AddField(model_name='subscriptionplan', name='name_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='subscriptionplan', name='name_en', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='subscriptionplan', name='description_ru', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='subscriptionplan', name='description_en', field=models.TextField(blank=True, default='')),

        migrations.AddField(model_name='gamecategory', name='name_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='gamecategory', name='name_en', field=models.CharField(blank=True, default='', max_length=150)),

        migrations.AddField(model_name='gameitem', name='title_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='gameitem', name='title_en', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='gameitem', name='description_ru', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='gameitem', name='description_en', field=models.TextField(blank=True, default='')),

        migrations.AddField(model_name='shopcategory', name='name_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='shopcategory', name='name_en', field=models.CharField(blank=True, default='', max_length=150)),

        migrations.AddField(model_name='shopitem', name='title_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='shopitem', name='title_en', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='shopitem', name='description_ru', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='shopitem', name='description_en', field=models.TextField(blank=True, default='')),

        migrations.AddField(model_name='blogcategory', name='name_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='blogcategory', name='name_en', field=models.CharField(blank=True, default='', max_length=150)),

        migrations.AddField(model_name='blogpost', name='title_ru', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='blogpost', name='title_en', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='blogpost', name='short_description_ru', field=models.CharField(blank=True, default='', max_length=500)),
        migrations.AddField(model_name='blogpost', name='short_description_en', field=models.CharField(blank=True, default='', max_length=500)),
        migrations.AddField(model_name='blogpost', name='content_ru', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='blogpost', name='content_en', field=models.TextField(blank=True, default='')),

        migrations.AddField(model_name='parentstorecategory', name='name_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='parentstorecategory', name='name_en', field=models.CharField(blank=True, default='', max_length=150)),

        migrations.AddField(model_name='parentstorepromobanner', name='kicker_ru', field=models.CharField(blank=True, default='', max_length=80)),
        migrations.AddField(model_name='parentstorepromobanner', name='kicker_en', field=models.CharField(blank=True, default='', max_length=80)),
        migrations.AddField(model_name='parentstorepromobanner', name='title_ru', field=models.CharField(blank=True, default='', max_length=160)),
        migrations.AddField(model_name='parentstorepromobanner', name='title_en', field=models.CharField(blank=True, default='', max_length=160)),
        migrations.AddField(model_name='parentstorepromobanner', name='subtitle_ru', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='parentstorepromobanner', name='subtitle_en', field=models.CharField(blank=True, default='', max_length=255)),

        migrations.AddField(model_name='parentnotification', name='title_ru', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='parentnotification', name='title_en', field=models.CharField(blank=True, default='', max_length=150)),
        migrations.AddField(model_name='parentnotification', name='body_ru', field=models.CharField(blank=True, default='', max_length=500)),
        migrations.AddField(model_name='parentnotification', name='body_en', field=models.CharField(blank=True, default='', max_length=500)),

        migrations.AddField(model_name='notificationrule', name='title_ru', field=models.CharField(blank=True, default='', max_length=200)),
        migrations.AddField(model_name='notificationrule', name='title_en', field=models.CharField(blank=True, default='', max_length=200)),
        migrations.AddField(model_name='notificationrule', name='body_ru', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='notificationrule', name='body_en', field=models.TextField(blank=True, default='')),
    ]
