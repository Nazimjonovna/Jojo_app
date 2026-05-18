import random
import string

from django.contrib.auth.models import AbstractUser, Group, Permission, BaseUserManager
from django.db import models
from django.utils import timezone


def generate_numeric_code(length=6):
    return "".join(random.choices(string.digits, k=length))


class UserManager(BaseUserManager):
    def create_user(self, phone=None, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number is required")

        user = self.model(phone=phone, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, phone=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "parent")
        extra_fields.setdefault("language", "uz_latn")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(phone=phone, password=password, **extra_fields)


class User(AbstractUser):
    ROLE_PARENT = "parent"
    ROLE_CHILD = "child"

    GENDER_MALE = "male"
    GENDER_FEMALE = "female"

    ROLE_CHOICES = (
        (ROLE_PARENT, "Parent"),
        (ROLE_CHILD, "Child"),
    )

    GENDER_CHOICES = (
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
    )

    LANGUAGE_CHOICES = (
        ("uz_latn", "O‘zbek lotin"),
        ("uz_cyrl", "Ўзбек кирилл"),
        ("ru", "Русский"),
        ("en", "English"),
    )

    username = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    phone = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
    )

    full_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_PARENT,
    )

    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
    )

    language = models.CharField(
        max_length=20,
        choices=LANGUAGE_CHOICES,
        default="uz_latn",
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
    )

    # Child uchun
    age = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    groups = models.ManyToManyField(
        Group,
        verbose_name="groups",
        blank=True,
        related_name="jojo_user_groups",
        related_query_name="jojo_user",
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name="user permissions",
        blank=True,
        related_name="jojo_user_permissions",
        related_query_name="jojo_user_permission",
    )

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        if self.phone:
            return f"{self.phone} - {self.role}"
        return f"{self.id} - {self.role}"


class OTPCode(models.Model):
    phone = models.CharField(max_length=20)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    # 3-marta xato kiritilsa block
    attempt_count = models.PositiveIntegerField(default=0)
    first_attempt_at = models.DateTimeField(null=True, blank=True)
    blocked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_blocked(self):
        return self.blocked_until and timezone.now() < self.blocked_until

    def block_time_left_seconds(self):
        if not self.blocked_until:
            return 0

        seconds = int((self.blocked_until - timezone.now()).total_seconds())
        return max(seconds, 0)

    def __str__(self):
        return f"{self.phone} - {self.code}"


class PairingCode(models.Model):
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pairing_codes",
    )

    # Figma’dagi BFKY4Y kabi kod uchun 6 belgili string
    code = models.CharField(max_length=10, unique=True)

    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    child_name = models.CharField(max_length=255, null=True, blank=True)
    child_gender = models.CharField(
        max_length=20,
        choices=User.GENDER_CHOICES,
        null=True,
        blank=True,
    )
    child_age = models.PositiveIntegerField(null=True, blank=True)
    child_avatar = models.ImageField(
        upload_to="children/",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.parent_id} - {self.code}"


class ParentChild(models.Model):
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="children_links",
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_links",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("parent", "child")
        verbose_name = "Parent Child"
        verbose_name_plural = "Parent Children"

    def __str__(self):
        return f"Parent {self.parent_id} -> Child {self.child_id}"


class ChildLocation(models.Model):
    SOURCE_REST = "rest"
    SOURCE_WEBSOCKET = "websocket"

    SOURCE_CHOICES = (
        (SOURCE_REST, "REST"),
        (SOURCE_WEBSOCKET, "WebSocket"),
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="locations",
    )

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    accuracy = models.FloatField(null=True, blank=True)
    battery_level = models.IntegerField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_REST,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.child_id}: {self.latitude}, {self.longitude}"


class ChildLastLocation(models.Model):
    child = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="last_location",
    )

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    accuracy = models.FloatField(null=True, blank=True)
    battery_level = models.IntegerField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.child_id}: {self.latitude}, {self.longitude}"


class SafeRoute(models.Model):
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="safe_routes",
    )

    name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)

    color = models.CharField(max_length=20, default="#4F46E5")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - parent {self.parent_id}"


class SafeRoutePoint(models.Model):
    route = models.ForeignKey(
        SafeRoute,
        on_delete=models.CASCADE,
        related_name="points",
    )

    order = models.PositiveIntegerField(default=0)

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    title = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.route_id} - {self.order}"


class ChildRouteAssignment(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_FINISHED, "Finished"),
    )

    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="route_assignments",
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="assigned_routes",
    )

    route = models.ForeignKey(
        SafeRoute,
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    allowed_radius_meters = models.PositiveIntegerField(default=100)

    notify_on_deviation = models.BooleanField(default=True)

    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    days_of_week = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("child", "route", "status")

    def __str__(self):
        return f"{self.child_id} -> {self.route_id}"


class RouteAlert(models.Model):
    ALERT_OFF_ROUTE = "off_route"
    ALERT_BACK_TO_ROUTE = "back_to_route"

    ALERT_CHOICES = (
        (ALERT_OFF_ROUTE, "Off route"),
        (ALERT_BACK_TO_ROUTE, "Back to route"),
    )

    assignment = models.ForeignKey(
        ChildRouteAssignment,
        on_delete=models.CASCADE,
        related_name="alerts",
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="route_alerts",
    )

    alert_type = models.CharField(
        max_length=30,
        choices=ALERT_CHOICES,
    )

    distance_meters = models.FloatField(null=True, blank=True)

    location = models.ForeignKey(
        ChildLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.child_id} - {self.alert_type}"


class DeviceToken(models.Model):
    DEVICE_ANDROID = "android"
    DEVICE_IOS = "ios"

    DEVICE_CHOICES = (
        (DEVICE_ANDROID, "Android"),
        (DEVICE_IOS, "iOS"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )

    device_id = models.CharField(
        max_length=255,
        db_index=True,
    )

    # Firebase FCM token
    token = models.TextField()

    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_CHOICES,
        default=DEVICE_ANDROID,
    )

    is_active = models.BooleanField(default=True)

    last_login_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "device_id"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.device_type} - {self.device_id}"