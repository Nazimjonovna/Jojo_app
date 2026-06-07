from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0015_parent_notifications"),
    ]

    operations = [
        migrations.AlterField(
            model_name="parentnotification",
            name="category",
            field=models.CharField(
                choices=[
                    ("zone_in", "Zone in"),
                    ("zone_out", "Zone out"),
                    ("zone_transition", "Zone transition"),
                    ("destination", "Destination"),
                    ("battery", "Battery"),
                    ("offline", "Offline"),
                    ("login", "Login"),
                    ("order", "Order"),
                    ("shipping", "Shipping"),
                    ("deal", "Deal"),
                    ("screen", "Screen time"),
                    ("premium", "Premium"),
                    ("tip", "Tip"),
                    ("route", "Route"),
                    ("place_recommendation", "Place recommendation"),
                    ("system", "System"),
                    ("sos", "SOS"),
                ],
                max_length=32,
            ),
        ),
    ]
