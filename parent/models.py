import random
import string
from datetime import timedelta
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

    CHILD_STATUS_ACTIVE = "active"
    CHILD_STATUS_NON_ACTIVE = "non_active"

    CHILD_STATUS_CHOICES = (
        (CHILD_STATUS_ACTIVE, "Active"),
        (CHILD_STATUS_NON_ACTIVE, "Non active"),
    )

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
    age = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    child_status = models.CharField(
        max_length=20,
        choices=CHILD_STATUS_CHOICES,
        default=CHILD_STATUS_ACTIVE,
    )
    pending_delete_at = models.DateTimeField(
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
    is_premium = models.BooleanField(default=False)
    premium_expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def has_active_premium(self):
        if not self.is_premium:
            return False

        if not self.premium_expires_at:
            return True

        return timezone.now() < self.premium_expires_at

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        if self.phone:
            return f"{self.phone} - {self.role}"
        return f"{self.id} - {self.role}"

    def is_child_pending_expired(self):
        if self.role != self.ROLE_CHILD:
            return False

        if self.child_status != self.CHILD_STATUS_NON_ACTIVE:
            return False

        if not self.pending_delete_at:
            return False

        return timezone.now() >= self.pending_delete_at

    def pending_delete_time_left_seconds(self):
        if not self.pending_delete_at:
            return None

        seconds = int((self.pending_delete_at - timezone.now()).total_seconds())
        return max(seconds, 0)


class OTPCode(models.Model):
    phone = models.CharField(max_length=20)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

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

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="child_pairing_codes",
        null=True,
        blank=True,
    )

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

    PROVIDER_GPS = "gps"
    PROVIDER_FUSED = "fused"
    PROVIDER_NETWORK = "network"
    PROVIDER_PASSIVE = "passive"

    PROVIDER_CHOICES = (
        (PROVIDER_GPS, "GPS"),
        (PROVIDER_FUSED, "Fused"),
        (PROVIDER_NETWORK, "Network"),
        (PROVIDER_PASSIVE, "Passive"),
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="locations",
    )

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    accuracy = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    altitude_accuracy = models.FloatField(null=True, blank=True)

    battery_level = models.IntegerField(null=True, blank=True)
    is_charging = models.BooleanField(null=True, blank=True)

    speed = models.FloatField(null=True, blank=True, help_text="m/s")
    speed_accuracy = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)

    signal_strength = models.IntegerField(
        null=True,
        blank=True,
        help_text="0..4 ASU yoki -100..-50 dBm asosida 0..4 ko‘rsatkich.",
    )
    network_type = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="wifi/cellular/none",
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        blank=True,
        default="",
    )

    is_mock_location = models.BooleanField(default=False)

    activity_type = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="still/walking/running/in_vehicle/on_bicycle/unknown",
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_REST,
    )

    # Klient tomondagi cheklov-vaqtni saqlash — batch yuborilganda kerak.
    captured_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["child", "-created_at"], name="child_loc_recent_idx"),
            models.Index(fields=["child", "created_at"], name="child_loc_range_idx"),
        ]

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
    altitude = models.FloatField(null=True, blank=True)

    battery_level = models.IntegerField(null=True, blank=True)
    is_charging = models.BooleanField(null=True, blank=True)

    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)

    signal_strength = models.IntegerField(null=True, blank=True)
    network_type = models.CharField(max_length=20, blank=True, default="")

    activity_type = models.CharField(max_length=20, blank=True, default="")
    provider = models.CharField(max_length=20, blank=True, default="")

    captured_at = models.DateTimeField(null=True, blank=True)

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


class SavedLocation(models.Model):
    LOCATION_HOME = "home"
    LOCATION_SCHOOL = "school"
    LOCATION_OTHER = "other"
    LOCATION_TYPE_CHOICES = (
        (LOCATION_HOME, "Home"),
        (LOCATION_SCHOOL, "School"),
        (LOCATION_OTHER, "Other"),
    )
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_saved_locations",
        related_query_name="parent_saved_location",
    )
    name = models.CharField(max_length=150)
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPE_CHOICES,
        default=LOCATION_OTHER,
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    radius_meters = models.PositiveIntegerField(default=100)
    address = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - parent {self.parent_id}"
    
    
class GameCategory(models.Model):
    name = models.CharField(max_length=150)
    icon = models.ImageField(
        upload_to="games/categories/",
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class GameItem(models.Model):
    category = models.ForeignKey(
        GameCategory,
        on_delete=models.CASCADE,
        related_name="games"
    )

    title = models.CharField(max_length=150)

    description = models.TextField(
        null=True,
        blank=True
    )

    thumbnail = models.ImageField(
        upload_to="games/thumbnails/",
        null=True,
        blank=True
    )

    banner = models.ImageField(
        upload_to="games/banners/",
        null=True,
        blank=True
    )

    # Agar o‘yin webview orqali ochilsa
    game_url = models.URLField(
        null=True,
        blank=True
    )

    # Agar Flutter ichida local screen ochilsa
    screen_key = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    age_min = models.PositiveIntegerField(default=1)
    age_max = models.PositiveIntegerField(default=18)

    reward_points = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.title


class ShopCategory(models.Model):
    name = models.CharField(max_length=150)

    icon = models.ImageField(
        upload_to="shop/categories/",
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class ShopItem(models.Model):
    category = models.ForeignKey(
        ShopCategory,
        on_delete=models.CASCADE,
        related_name="items"
    )

    title = models.CharField(max_length=150)

    description = models.TextField(
        null=True,
        blank=True
    )

    image = models.ImageField(
        upload_to="shop/items/",
        null=True,
        blank=True
    )

    price_points = models.PositiveIntegerField(default=0)

    old_price_points = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    stock = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    age_min = models.PositiveIntegerField(default=1)
    age_max = models.PositiveIntegerField(default=18)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def has_discount(self):
        return (
            self.old_price_points is not None
            and self.old_price_points > self.price_points
            and self.price_points >= 0
        )

    def discount_percent(self):
        if not self.has_discount():
            return 0
        return round(
            ((self.old_price_points - self.price_points) / self.old_price_points) * 100
        )

    def __str__(self):
        return self.title


class ChildWallet(models.Model):
    child = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wallet"
    )

    balance = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.child_id} - {self.balance}"


class ChildTransaction(models.Model):
    TYPE_EARN = "earn"
    TYPE_SPEND = "spend"

    TYPE_CHOICES = (
        (TYPE_EARN, "Earn"),
        (TYPE_SPEND, "Spend"),
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    amount = models.IntegerField()

    transaction_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    source = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    description = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.child_id} - {self.transaction_type} - {self.amount}"


class ShopPurchase(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shop_purchases"
    )

    item = models.ForeignKey(
        ShopItem,
        on_delete=models.CASCADE,
        related_name="purchases"
    )

    price_points = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.child_id} - {self.item_id} - {self.status}"


class SOSAlert(models.Model):
    STATUS_NEW = "new"
    STATUS_VIEWED = "viewed"
    STATUS_RESOLVED = "resolved"

    STATUS_CHOICES = (
        (STATUS_NEW, "New"),
        (STATUS_VIEWED, "Viewed"),
        (STATUS_RESOLVED, "Resolved"),
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sos_alerts"
    )

    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_sos_alerts"
    )

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )

    address = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    note = models.TextField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SOS {self.child_id} -> {self.parent_id}"
    
    
class ChildInstalledApp(models.Model):
    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="installed_apps"
    )

    app_name = models.CharField(max_length=150)
    package_name = models.CharField(max_length=255)

    category = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    is_system_app = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    last_synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("child", "package_name")
        ordering = ["app_name"]

    def __str__(self):
        return f"{self.child_id} - {self.app_name}"


class ChildAppUsage(models.Model):
    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="app_usages"
    )

    app = models.ForeignKey(
        ChildInstalledApp,
        on_delete=models.CASCADE,
        related_name="usages"
    )

    usage_date = models.DateField()

    total_usage_seconds = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)

    first_opened_at = models.DateTimeField(null=True, blank=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("child", "app", "usage_date")
        ordering = ["-usage_date", "-total_usage_seconds"]

    def __str__(self):
        return f"{self.child_id} - {self.app.package_name} - {self.usage_date}"


class ChildAppLimit(models.Model):
    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="app_limits"
    )

    app = models.OneToOneField(
        ChildInstalledApp,
        on_delete=models.CASCADE,
        related_name="limit"
    )

    daily_limit_seconds = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_child_app_limits"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def daily_limit_minutes(self):
        return round(self.daily_limit_seconds / 60)

    def __str__(self):
        return f"{self.child_id} - {self.app.package_name} - {self.daily_limit_seconds}s"


class ChildBlockedApp(models.Model):
    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocked_apps"
    )

    app = models.OneToOneField(
        ChildInstalledApp,
        on_delete=models.CASCADE,
        related_name="block"
    )

    is_blocked = models.BooleanField(default=True)

    reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_child_app_blocks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.child_id} - {self.app.package_name} - blocked={self.is_blocked}"
    
    
class AppVersion(models.Model):
    PLATFORM_ANDROID = "android"
    PLATFORM_IOS = "ios"

    PLATFORM_CHOICES = (
        (PLATFORM_ANDROID, "Android"),
        (PLATFORM_IOS, "iOS"),
    )

    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES
    )

    latest_version = models.CharField(max_length=30)
    min_supported_version = models.CharField(max_length=30)

    force_update = models.BooleanField(default=False)

    update_url = models.URLField(
        null=True,
        blank=True
    )

    title = models.CharField(
        max_length=150,
        default="Update available"
    )

    message = models.TextField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.platform} - {self.latest_version}"


class ChildDailyActivity(models.Model):
    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="daily_activities"
    )

    activity_date = models.DateField()

    distance_meters = models.PositiveIntegerField(default=0)
    steps_count = models.PositiveIntegerField(default=0)
    active_seconds = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("child", "activity_date")
        ordering = ["-activity_date"]

    def distance_km(self):
        return round(self.distance_meters / 1000, 2)

    def __str__(self):
        return f"{self.child_id} - {self.activity_date}"


class SavedLocationVisit(models.Model):
    saved_location = models.ForeignKey(
        SavedLocation,
        on_delete=models.CASCADE,
        related_name="visits"
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_location_visits"
    )

    visit_count = models.PositiveIntegerField(default=0)

    last_visited_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("saved_location", "child")

    def __str__(self):
        return f"{self.child_id} - {self.saved_location_id} - {self.visit_count}"
    
    
class ChildSavedLocationState(models.Model):
    child = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="saved_location_state"
    )

    current_location = models.ForeignKey(
        SavedLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_children"
    )

    previous_location = models.ForeignKey(
        SavedLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="previous_children"
    )

    last_event_type = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    last_event_at = models.DateTimeField(
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.child_id} current={self.current_location_id}"


class ChildSavedLocationEvent(models.Model):
    EVENT_ENTER = "enter"
    EVENT_EXIT = "exit"
    EVENT_MOVING_HOME_TO_SCHOOL = "moving_home_to_school"
    EVENT_MOVING_SCHOOL_TO_HOME = "moving_school_to_home"

    EVENT_CHOICES = (
        (EVENT_ENTER, "Enter"),
        (EVENT_EXIT, "Exit"),
        (EVENT_MOVING_HOME_TO_SCHOOL, "Moving home to school"),
        (EVENT_MOVING_SCHOOL_TO_HOME, "Moving school to home"),
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_location_events"
    )

    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="child_saved_location_events"
    )

    saved_location = models.ForeignKey(
        SavedLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events"
    )

    event_type = models.CharField(
        max_length=50,
        choices=EVENT_CHOICES
    )

    title = models.CharField(max_length=150)
    body = models.TextField()

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.child_id} - {self.event_type}"
    
    
class SubscriptionPlan(models.Model):
    PERIOD_DAYS = "days"
    PERIOD_MONTHS = "months"
    PERIOD_YEARS = "years"

    PERIOD_CHOICES = (
        (PERIOD_DAYS, "Days"),
        (PERIOD_MONTHS, "Months"),
        (PERIOD_YEARS, "Years"),
    )

    name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)

    price = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=10, default="UZS")

    duration_value = models.PositiveIntegerField(default=1)
    duration_type = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        default=PERIOD_MONTHS,
    )

    is_trial = models.BooleanField(default=False)
    trial_days = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "price"]

    def __str__(self):
        if self.is_trial:
            return f"{self.name} - Trial {self.trial_days} days"
        return f"{self.name} - {self.price} {self.currency}"

    def calculate_expires_at(self, start_date=None):
        start_date = start_date or timezone.now()

        if self.is_trial:
            return start_date + timedelta(days=self.trial_days)

        if self.duration_type == self.PERIOD_DAYS:
            return start_date + timedelta(days=self.duration_value)

        if self.duration_type == self.PERIOD_MONTHS:
            return start_date + timedelta(days=30 * self.duration_value)

        if self.duration_type == self.PERIOD_YEARS:
            return start_date + timedelta(days=365 * self.duration_value)

        return start_date


class UserSubscription(models.Model):
    STATUS_TRIAL = "trial"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    SOURCE_TRIAL = "trial"
    SOURCE_ADMIN = "admin"
    SOURCE_PAYMENT = "payment"

    SOURCE_CHOICES = (
        (SOURCE_TRIAL, "Trial"),
        (SOURCE_ADMIN, "Admin"),
        (SOURCE_PAYMENT, "Payment"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_subscriptions",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_TRIAL,
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_TRIAL,
    )

    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_subscriptions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expires_at"]

    def is_active_now(self):
        return (
            self.status in [self.STATUS_TRIAL, self.STATUS_ACTIVE]
            and self.expires_at
            and timezone.now() < self.expires_at
        )

    def days_left(self):
        if not self.expires_at:
            return 0

        seconds = (self.expires_at - timezone.now()).total_seconds()
        return max(round(seconds / 86400, 1), 0)

    def __str__(self):
        return f"{self.user_id} - {self.status} - {self.expires_at}"


class SubscriptionPayment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscription_payments",
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    amount = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=10, default="UZS")

    provider = models.CharField(max_length=50, null=True, blank=True)
    provider_transaction_id = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    raw_payload = models.JSONField(default=dict, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} - {self.amount} {self.currency} - {self.status}"
    
    
class CallCenterTicket(models.Model):
    STATUS_NEW = "new"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_WAITING = "waiting"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"
    STATUS_BLOCKED = "blocked"

    STATUS_CHOICES = (
        (STATUS_NEW, "Yangi"),
        (STATUS_IN_PROGRESS, "Jarayonda"),
        (STATUS_WAITING, "Kutilmoqda"),
        (STATUS_RESOLVED, "Hal qilingan"),
        (STATUS_CLOSED, "Yopilgan"),
        (STATUS_BLOCKED, "Bloklangan"),
    )

    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="call_center_tickets",
    )

    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator_tickets",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )

    title = models.CharField(
        max_length=255,
        default="Foydalanuvchi murojaati"
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    priority = models.CharField(
        max_length=20,
        default="normal",
    )

    last_contact_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.parent_id} - {self.status}"


class CallCenterComment(models.Model):
    ticket = models.ForeignKey(
        CallCenterTicket,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="call_center_comments",
    )

    comment = models.TextField()

    old_status = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    new_status = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket_id} - {self.operator_id}"


class BlogCategory(models.Model):
    name = models.CharField(max_length=150)
    icon = models.ImageField(
        upload_to="blog/categories/",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Blog Category"
        verbose_name_plural = "Blog Categories"

    def __str__(self):
        return self.name


class BlogPost(models.Model):
    TYPE_BLOG = "blog"
    TYPE_VIDEO = "video"

    TYPE_CHOICES = (
        (TYPE_BLOG, "Blog"),
        (TYPE_VIDEO, "Video"),
    )

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )

    title = models.CharField(max_length=255)

    short_description = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    content = models.TextField(
        null=True,
        blank=True,
    )

    post_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_BLOG,
    )

    thumbnail = models.ImageField(
        upload_to="blog/thumbnails/",
        null=True,
        blank=True,
    )

    banner = models.ImageField(
        upload_to="blog/banners/",
        null=True,
        blank=True,
    )

    video_url = models.URLField(
        null=True,
        blank=True,
    )

    video_file = models.FileField(
        upload_to="blog/videos/",
        null=True,
        blank=True,
    )

    external_url = models.URLField(
        null=True,
        blank=True,
    )

    reading_time_minutes = models.PositiveIntegerField(default=5)

    duration_label = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Video davomiyligi, masalan '11:38'. Faqat video uchun.",
    )

    likes_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-published_at", "-created_at"]
        verbose_name = "Blog / Video"
        verbose_name_plural = "Blogs / Videos"

    def __str__(self):
        return self.title


class BlogPostSave(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_blog_posts",
    )

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="saved_by_users",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} - {self.post_id}"


class BlogPostLike(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="liked_blog_posts",
    )

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name="liked_by_users",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} - {self.post_id}"
# ============================================================================
# Parent Store (Do‘kon) — STEM o‘yinchoq, kitob va boshqalar.
# Kids ShopItem/ShopCategory dan farqi: pul birligi so‘m, real buyurtma
# yetkazib berish, ko‘p surat/video galereya va promo bannerlar bilan.
# ============================================================================


class ParentStoreCategory(models.Model):
    TYPE_STEM = "stem"
    TYPE_BOOK = "book"
    TYPE_OTHER = "other"

    TYPE_CHOICES = (
        (TYPE_STEM, "STEM"),
        (TYPE_BOOK, "Kitob"),
        (TYPE_OTHER, "Boshqa"),
    )

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    product_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_OTHER,
    )
    icon = models.ImageField(
        upload_to="parent_store/categories/",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Parent Store Category"
        verbose_name_plural = "Parent Store Categories"

    def __str__(self):
        return self.name


class ParentStoreProduct(models.Model):
    BADGE_NONE = "none"
    BADGE_TOP = "top"
    BADGE_YANGI = "yangi"

    BADGE_CHOICES = (
        (BADGE_NONE, "Belgi yo‘q"),
        (BADGE_TOP, "TOP"),
        (BADGE_YANGI, "YANGI"),
    )

    category = models.ForeignKey(
        ParentStoreCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    category_label = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Kartochkada chiqadigan kichik label, masalan STEM O‘YINCHOQ",
    )

    age_label = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Masalan 6+ yosh",
    )

    price = models.PositiveIntegerField(help_text="so‘m")
    old_price = models.PositiveIntegerField(null=True, blank=True)

    badge = models.CharField(
        max_length=10,
        choices=BADGE_CHOICES,
        default=BADGE_NONE,
    )

    features = models.JSONField(
        default=list,
        blank=True,
        help_text="String list, masalan [\"Bluetooth\", \"50+ daraja\"]",
    )

    short_description = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    description = models.TextField(blank=True, default="")

    thumbnail = models.ImageField(
        upload_to="parent_store/products/thumbnails/",
        null=True,
        blank=True,
    )

    video_url = models.URLField(blank=True, default="")

    video_file = models.FileField(
        upload_to="parent_store/products/videos/",
        null=True,
        blank=True,
    )

    deal_ends_at = models.DateTimeField(null=True, blank=True)

    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    placeholder_label = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Surat yuklanmaganda ko‘rsatiladigan label (offline placeholder).",
    )
    placeholder_tint = models.CharField(
        max_length=9,
        blank=True,
        default="",
        help_text="Placeholder fon rangi, hex (#RRGGBB).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name = "Parent Store Product"
        verbose_name_plural = "Parent Store Products"

    def __str__(self):
        return self.name

    @property
    def has_video(self):
        return bool(self.video_url) or bool(self.video_file)

    @property
    def discount_percent(self):
        if not self.old_price or self.old_price <= self.price:
            return 0
        return round(((self.old_price - self.price) / self.old_price) * 100)


class ParentStoreProductImage(models.Model):
    product = models.ForeignKey(
        ParentStoreProduct,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="parent_store/products/gallery/")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.product_id} #{self.order}"


class ParentStorePromoBanner(models.Model):
    THEME_CREAM = "cream"
    THEME_SKY = "sky"
    THEME_GREEN = "green"

    THEME_CHOICES = (
        (THEME_CREAM, "Cream"),
        (THEME_SKY, "Sky"),
        (THEME_GREEN, "Green"),
    )

    kicker = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=255, blank=True, default="")
    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default=THEME_CREAM,
    )

    image = models.ImageField(
        upload_to="parent_store/banners/",
        null=True,
        blank=True,
    )

    link_product = models.ForeignKey(
        ParentStoreProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Banner bosilganda ochiladigan mahsulot.",
    )

    link_category_type = models.CharField(
        max_length=20,
        choices=ParentStoreCategory.TYPE_CHOICES,
        blank=True,
        default="",
        help_text="Mahsulot biriktirilmagan bo‘lsa, banner bosilganda filtrlanadigan tip.",
    )

    gift_icon = models.BooleanField(default=False)

    placeholder_label = models.CharField(max_length=40, blank=True, default="")
    placeholder_tint = models.CharField(max_length=9, blank=True, default="")

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Parent Store Promo Banner"
        verbose_name_plural = "Parent Store Promo Banners"

    def __str__(self):
        return self.title


class ParentStoreSavedProduct(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_store_saved",
    )
    product = models.ForeignKey(
        ParentStoreProduct,
        on_delete=models.CASCADE,
        related_name="saved_by_users",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} - {self.product_id}"


class ParentStoreOrder(models.Model):
    STATUS_SENT = "sent"
    STATUS_REVIEW = "review"
    STATUS_CONFIRMED = "confirmed"
    STATUS_SHIPPING = "shipping"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_SENT, "Yuborildi"),
        (STATUS_REVIEW, "Ko‘rib chiqilmoqda"),
        (STATUS_CONFIRMED, "Tasdiqlandi"),
        (STATUS_SHIPPING, "Yetkazilmoqda"),
        (STATUS_DELIVERED, "Yetkazildi"),
        (STATUS_CANCELLED, "Bekor qilindi"),
    )

    ACTIVE_STATUSES = (
        STATUS_SENT,
        STATUS_REVIEW,
        STATUS_CONFIRMED,
        STATUS_SHIPPING,
    )

    code = models.CharField(
        max_length=24,
        unique=True,
        help_text="Foydalanuvchiga ko‘rsatiladigan buyurtma raqami, masalan JOJ-1043",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_store_orders",
    )

    product = models.ForeignKey(
        ParentStoreProduct,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.PositiveIntegerField(
        help_text="Buyurtma yaratilgan paytdagi mahsulot narxi (so‘m).",
    )

    total_price = models.PositiveIntegerField()

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_SENT,
    )

    contact_phone = models.CharField(max_length=20, blank=True, default="")
    contact_name = models.CharField(max_length=150, blank=True, default="")
    address = models.TextField(blank=True, default="")
    note = models.TextField(blank=True, default="")

    sent_at = models.DateTimeField(null=True, blank=True)
    review_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipping_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Parent Store Order"
        verbose_name_plural = "Parent Store Orders"

    def __str__(self):
        return self.code

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def status_timestamps(self):
        return {
            self.STATUS_SENT: self.sent_at,
            self.STATUS_REVIEW: self.review_at,
            self.STATUS_CONFIRMED: self.confirmed_at,
            self.STATUS_SHIPPING: self.shipping_at,
            self.STATUS_DELIVERED: self.delivered_at,
            self.STATUS_CANCELLED: self.cancelled_at,
        }

    def stamp_status(self, status_value, when=None):
        when = when or timezone.now()
        field = {
            self.STATUS_SENT: "sent_at",
            self.STATUS_REVIEW: "review_at",
            self.STATUS_CONFIRMED: "confirmed_at",
            self.STATUS_SHIPPING: "shipping_at",
            self.STATUS_DELIVERED: "delivered_at",
            self.STATUS_CANCELLED: "cancelled_at",
        }.get(status_value)
        if field:
            setattr(self, field, when)
        self.status = status_value


def generate_parent_store_order_code():
    """JOJ-XXXX shaklidagi keyingi tartib raqamini qaytaradi."""
    last = ParentStoreOrder.objects.order_by("-id").first()
    next_id = (last.id + 1) if last else 1
    return f"JOJ-{1000 + next_id}"



# ============================================================================
# Tracking: Frequent places & place recommendations
# Bola joylashuvlari ustida clustering qilib, ko‘p tashrif buyuradigan
# joylarni topib ota-onaga "Saved location'ga qo‘shing" tavsiyasi beradi.
# ============================================================================


class ChildFrequentPlace(models.Model):
    """Clusterlanган hotspot. Bir nuqta — bir cluster (DBSCAN/grid asosida)."""

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="frequent_places",
    )

    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="children_frequent_places",
        null=True,
        blank=True,
    )

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    radius_meters = models.PositiveIntegerField(default=120)

    visit_count = models.PositiveIntegerField(default=0)
    total_dwell_seconds = models.PositiveIntegerField(default=0)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    label = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Avtomatik label (masalan, 'Doim boriladigan joy').",
    )

    is_recommendation_dismissed = models.BooleanField(default=False)
    saved_location = models.ForeignKey(
        "SavedLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frequent_places",
        help_text="Agar ota-ona uni saved location'ga aylantirgan bo‘lsa.",
    )

    class Meta:
        ordering = ["-visit_count", "-last_seen_at"]
        indexes = [
            models.Index(fields=["child", "-visit_count"], name="child_fp_visit_idx"),
        ]

    def __str__(self):
        return f"#{self.id} child={self.child_id} visits={self.visit_count}"


class ChildDestinationPrediction(models.Model):
    """Bola yo'lda yurganida 'X tomon ketayapti' bashorati audit logi."""

    EVENT_HEADING_TO = "heading_to"
    EVENT_ARRIVING_SOON = "arriving_soon"

    EVENT_CHOICES = (
        (EVENT_HEADING_TO, "Heading to"),
        (EVENT_ARRIVING_SOON, "Arriving soon"),
    )

    child = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="destination_predictions",
    )
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="children_destination_predictions",
    )
    saved_location = models.ForeignKey(
        "SavedLocation",
        on_delete=models.CASCADE,
        related_name="destination_predictions",
    )
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_CHOICES,
        default=EVENT_HEADING_TO,
    )

    distance_meters = models.FloatField()
    speed_kmh = models.FloatField(null=True, blank=True)
    eta_seconds = models.FloatField(null=True, blank=True)

    title = models.CharField(max_length=120, blank=True, default="")
    body = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["child", "saved_location", "-created_at"],
                name="child_pred_recent_idx",
            ),
        ]

    def __str__(self):
        return f"{self.child_id} -> {self.saved_location_id} ({self.event_type})"


# ============================================================================
# Parent Notification Inbox — barcha eventlar (FCM, saved location, prediction,
# route alert, frequent place recommendation, store order) yagona joyga
# yoziladi. Ota-ona ilovasidagi "Bildirishnomalar" sahifasi shu jadvaldan
# o'qiydi va tarix sifatida saqlanadi.
# ============================================================================


class ParentNotification(models.Model):
    CATEGORY_ZONE_IN = "zone_in"
    CATEGORY_ZONE_OUT = "zone_out"
    CATEGORY_ZONE_TRANSITION = "zone_transition"
    CATEGORY_DESTINATION = "destination"
    CATEGORY_BATTERY = "battery"
    CATEGORY_OFFLINE = "offline"
    CATEGORY_LOGIN = "login"
    CATEGORY_ORDER = "order"
    CATEGORY_SHIPPING = "shipping"
    CATEGORY_DEAL = "deal"
    CATEGORY_SCREEN = "screen"
    CATEGORY_PREMIUM = "premium"
    CATEGORY_TIP = "tip"
    CATEGORY_ROUTE = "route"
    CATEGORY_PLACE_RECOMMENDATION = "place_recommendation"
    CATEGORY_SYSTEM = "system"
    CATEGORY_SOS = "sos"

    CATEGORY_CHOICES = (
        (CATEGORY_ZONE_IN, "Zone in"),
        (CATEGORY_ZONE_OUT, "Zone out"),
        (CATEGORY_ZONE_TRANSITION, "Zone transition"),
        (CATEGORY_DESTINATION, "Destination"),
        (CATEGORY_BATTERY, "Battery"),
        (CATEGORY_OFFLINE, "Offline"),
        (CATEGORY_LOGIN, "Login"),
        (CATEGORY_ORDER, "Order"),
        (CATEGORY_SHIPPING, "Shipping"),
        (CATEGORY_DEAL, "Deal"),
        (CATEGORY_SCREEN, "Screen time"),
        (CATEGORY_PREMIUM, "Premium"),
        (CATEGORY_TIP, "Tip"),
        (CATEGORY_ROUTE, "Route"),
        (CATEGORY_PLACE_RECOMMENDATION, "Place recommendation"),
        (CATEGORY_SYSTEM, "System"),
        (CATEGORY_SOS, "SOS"),
    )

    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_notifications",
    )
    child = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="related_parent_notifications",
    )

    category = models.CharField(
        max_length=32,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_SYSTEM,
    )

    title = models.CharField(max_length=150)
    body = models.CharField(max_length=500, blank=True, default="")

    data = models.JSONField(
        blank=True,
        default=dict,
        help_text="Marshrutlash uchun route/screen va eventga oid context.",
    )

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["parent", "is_read", "-created_at"],
                name="parent_notif_inbox_idx",
            ),
            models.Index(
                fields=["parent", "-created_at"],
                name="parent_notif_recent_idx",
            ),
        ]

    def __str__(self):
        return f"#{self.id} {self.category} -> parent {self.parent_id}"

    def mark_read(self, save=True):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=["is_read", "read_at"])
