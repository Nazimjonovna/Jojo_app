# Merge migration: birlashtirib qo'yamiz 0019 va 0022 leaf node'larini.
# 0020 noto'g'ri 0017'ga bog'langan edi (0018/0019 chain'i tashlab ketilgan).
# Bu fayl ikkala leaf'ni bitta nuqtaga olib keladi — Django chain'ni
# yana linear ko'radi.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parent', '0019_parentstoreproduct_category_label_en_and_more'),
        ('parent', '0022_callcentercomment_direction_and_more'),
    ]

    operations = []
