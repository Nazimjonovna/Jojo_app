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

    class Meta:
        ordering = ["created_at"]

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