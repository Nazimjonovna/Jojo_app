import re

from rest_framework import serializers

from .models import (
    User,
    PairingCode,
    ChildLocation,
    ChildLastLocation,
    DeviceToken,
    SafeRoute,
    SafeRoutePoint,
    ChildRouteAssignment,
    RouteAlert,
    SavedLocation,
    GameCategory,
    GameItem,
    ShopCategory,
    ShopItem,
    ChildWallet,
    ChildTransaction,
    ShopPurchase,
    SOSAlert,
    ChildInstalledApp,
    ChildAppUsage,
    ChildAppLimit,
    ChildBlockedApp,
)


PHONE_REGEX = r"^\+998\d{9}$"


class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        return value


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6)

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        return value

    def validate_code(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("SMS kod 6 xonali bo‘lishi kerak.")
        return value


class ParentRegisterSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(max_length=20)

    device_id = serializers.CharField(
        write_only=True,
        max_length=255,
        required=True
    )

    token = serializers.CharField(
        write_only=True,
        required=True
    )

    device_type = serializers.ChoiceField(
        write_only=True,
        choices=["android", "ios"],
        default="android"
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "gender",
            "language",
            "avatar",
            "device_id",
            "token",
            "device_type",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "phone": {
                "validators": []
            }
        }

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        return value

    def validate_full_name(self, value):
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("full_name juda qisqa.")
        return value

    def validate_device_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("device_id majburiy.")
        return value

    def validate_token(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Firebase token majburiy.")
        return value

    def create(self, validated_data):
        validated_data.pop("device_id", None)
        validated_data.pop("token", None)
        validated_data.pop("device_type", None)

        phone = validated_data.pop("phone")

        user = User.objects.create_user(
            phone=phone,
            username=phone,
            role=User.ROLE_PARENT,
            **validated_data
        )

        return user


class UpdateLanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(
        choices=["uz_latn", "uz_cyrl", "ru", "en"]
    )


class PairingCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PairingCode
        fields = [
            "id",
            "code",
            "expires_at",
            "is_used",
            "child_name",
            "child_gender",
            "child_age",
            "child_avatar",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "expires_at",
            "is_used",
            "created_at",
        ]


class CreateChildPairingSerializer(serializers.Serializer):
    child_name = serializers.CharField(
        max_length=255,
        required=True
    )

    child_gender = serializers.ChoiceField(
        choices=["male", "female"],
        required=True
    )

    child_age = serializers.IntegerField(
        min_value=1,
        max_value=18,
        required=True
    )

    child_avatar = serializers.ImageField(
        required=False,
        allow_null=True
    )

    def validate_child_name(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Bola ismi kamida 2 ta belgidan iborat bo‘lishi kerak."
            )

        return value


class ChildRegisterByCodeSerializer(serializers.Serializer):
    pairing_code = serializers.CharField(max_length=10)

    device_id = serializers.CharField(max_length=255, required=True)
    token = serializers.CharField(required=True)
    device_type = serializers.ChoiceField(
        choices=["android", "ios"],
        default="android",
    )

    def validate_pairing_code(self, value):
        value = value.strip().upper()
        if len(value) < 4:
            raise serializers.ValidationError("Pairing code noto‘g‘ri.")
        return value

    def validate_device_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("device_id majburiy.")
        return value

    def validate_token(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Firebase token majburiy.")
        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "username",
            "full_name",
            "first_name",
            "last_name",
            "role",
            "gender",
            "age",
            "language",
            "avatar",
        ]


class ChildLastLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChildLastLocation
        fields = [
            "latitude",
            "longitude",
            "accuracy",
            "battery_level",
            "speed",
            "heading",
            "updated_at",
        ]


class ChildSerializer(serializers.ModelSerializer):
    last_location = serializers.SerializerMethodField()
    pending_delete_time_left_seconds = serializers.SerializerMethodField()
    pending_delete_time_left_days = serializers.SerializerMethodField()
    pairing_code = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "username",
            "full_name",
            "first_name",
            "role",
            "gender",
            "age",
            "language",
            "avatar",
            "child_status",
            "pending_delete_at",
            "pending_delete_time_left_seconds",
            "pending_delete_time_left_days",
            "pairing_code",
            "last_location",
        ]

    def get_last_location(self, obj):
        try:
            return ChildLastLocationSerializer(obj.last_location).data
        except ChildLastLocation.DoesNotExist:
            return None

    def get_pending_delete_time_left_seconds(self, obj):
        if obj.role != User.ROLE_CHILD:
            return None

        if obj.child_status != User.CHILD_STATUS_NON_ACTIVE:
            return None

        return obj.pending_delete_time_left_seconds()

    def get_pending_delete_time_left_days(self, obj):
        seconds = self.get_pending_delete_time_left_seconds(obj)

        if seconds is None:
            return None

        return round(seconds / 86400, 2)

    def get_pairing_code(self, obj):
        if obj.role != User.ROLE_CHILD:
            return None

        if obj.child_status != User.CHILD_STATUS_NON_ACTIVE:
            return None

        pairing = obj.child_pairing_codes.filter(
            is_used=False
        ).order_by("-created_at").first()

        if not pairing:
            return None

        return {
            "id": pairing.id,
            "code": pairing.code,
            "expires_at": pairing.expires_at,
            "is_used": pairing.is_used,
            "created_at": pairing.created_at,
        }


class ChildLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChildLocation
        fields = [
            "id",
            "child",
            "latitude",
            "longitude",
            "accuracy",
            "battery_level",
            "speed",
            "heading",
            "source",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "child",
            "source",
            "created_at",
        ]

    def validate_latitude(self, value):
        if value < -90 or value > 90:
            raise serializers.ValidationError("Latitude -90 va 90 orasida bo‘lishi kerak.")
        return value

    def validate_longitude(self, value):
        if value < -180 or value > 180:
            raise serializers.ValidationError("Longitude -180 va 180 orasida bo‘lishi kerak.")
        return value

    def validate_battery_level(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Battery level 0 va 100 orasida bo‘lishi kerak.")
        return value


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = [
            "id",
            "device_id",
            "token",
            "device_type",
            "is_active",
            "last_login_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "last_login_at",
            "created_at",
            "updated_at",
        ]

    def validate_device_id(self, value):
        if not value:
            raise serializers.ValidationError("device_id majburiy.")
        return value

    def validate_token(self, value):
        if not value:
            raise serializers.ValidationError("Firebase token majburiy.")
        return value


class SafeRoutePointSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafeRoutePoint
        fields = [
            "id",
            "order",
            "latitude",
            "longitude",
            "title",
        ]


class SafeRouteSerializer(serializers.ModelSerializer):
    points = SafeRoutePointSerializer(many=True, required=False)

    class Meta:
        model = SafeRoute
        fields = [
            "id",
            "name",
            "description",
            "color",
            "is_active",
            "points",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        points_data = validated_data.pop("points", [])
        route = SafeRoute.objects.create(**validated_data)

        for index, point_data in enumerate(points_data):
            SafeRoutePoint.objects.create(
                route=route,
                order=point_data.get("order", index),
                latitude=point_data["latitude"],
                longitude=point_data["longitude"],
                title=point_data.get("title"),
            )

        return route

    def update(self, instance, validated_data):
        points_data = validated_data.pop("points", None)

        instance.name = validated_data.get("name", instance.name)
        instance.description = validated_data.get("description", instance.description)
        instance.color = validated_data.get("color", instance.color)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save()

        if points_data is not None:
            instance.points.all().delete()

            for index, point_data in enumerate(points_data):
                SafeRoutePoint.objects.create(
                    route=instance,
                    order=point_data.get("order", index),
                    latitude=point_data["latitude"],
                    longitude=point_data["longitude"],
                    title=point_data.get("title"),
                )

        return instance


class ChildRouteAssignmentSerializer(serializers.ModelSerializer):
    route = SafeRouteSerializer(read_only=True)

    route_id = serializers.PrimaryKeyRelatedField(
        queryset=SafeRoute.objects.all(),
        source="route",
        write_only=True,
    )

    child_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.ROLE_CHILD),
        source="child",
        write_only=True,
    )

    class Meta:
        model = ChildRouteAssignment
        fields = [
            "id",
            "child_id",
            "route_id",
            "route",
            "status",
            "allowed_radius_meters",
            "notify_on_deviation",
            "start_time",
            "end_time",
            "days_of_week",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class RouteAlertSerializer(serializers.ModelSerializer):
    child = ChildSerializer(read_only=True)
    route_name = serializers.CharField(
        source="assignment.route.name",
        read_only=True,
    )

    class Meta:
        model = RouteAlert
        fields = [
            "id",
            "child",
            "route_name",
            "alert_type",
            "distance_meters",
            "created_at",
        ]
        read_only_fields = fields


class CreateChildPairingSerializer(serializers.Serializer):
    child_name = serializers.CharField(
        max_length=255,
        required=True
    )

    child_gender = serializers.ChoiceField(
        choices=["male", "female"],
        required=True
    )

    child_age = serializers.IntegerField(
        min_value=1,
        max_value=18,
        required=True
    )

    child_avatar = serializers.ImageField(
        required=False,
        allow_null=True
    )

    def validate_child_name(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Bola ismi kamida 2 ta belgidan iborat bo‘lishi kerak."
            )

        return value

    def validate_child_age(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Bola yoshi kamida 1 bo‘lishi kerak."
            )

        if value > 18:
            raise serializers.ValidationError(
                "Bola yoshi 18 dan katta bo‘lmasligi kerak."
            )

        return value
    
    
class SavedLocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = SavedLocation
        fields = [
            "id",
            "name",
            "location_type",
            "latitude",
            "longitude",
            "radius_meters",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_latitude(self, value):
        if value < -90 or value > 90:
            raise serializers.ValidationError(
                "Latitude -90 va 90 orasida bo‘lishi kerak."
            )
        return value

    def validate_longitude(self, value):
        if value < -180 or value > 180:
            raise serializers.ValidationError(
                "Longitude -180 va 180 orasida bo‘lishi kerak."
            )
        return value

    def validate_radius_meters(self, value):
        if value < 10:
            raise serializers.ValidationError(
                "Radius kamida 10 metr bo‘lishi kerak."
            )

        if value > 10000:
            raise serializers.ValidationError(
                "Radius 10000 metrdan oshmasligi kerak."
            )

        return value
    
    
class GameCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GameCategory
        fields = [
            "id",
            "name",
            "icon",
            "is_active",
            "order",
            "created_at",
        ]


class GameItemSerializer(serializers.ModelSerializer):
    category = GameCategorySerializer(read_only=True)

    class Meta:
        model = GameItem
        fields = [
            "id",
            "category",
            "title",
            "description",
            "thumbnail",
            "banner",
            "game_url",
            "screen_key",
            "age_min",
            "age_max",
            "reward_points",
            "is_active",
            "is_featured",
            "order",
            "created_at",
            "updated_at",
        ]


class ShopCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopCategory
        fields = [
            "id",
            "name",
            "icon",
            "is_active",
            "order",
            "created_at",
        ]


class ShopItemSerializer(serializers.ModelSerializer):
    category = ShopCategorySerializer(read_only=True)

    class Meta:
        model = ShopItem
        fields = [
            "id",
            "category",
            "title",
            "description",
            "image",
            "price_points",
            "stock",
            "age_min",
            "age_max",
            "is_active",
            "is_featured",
            "order",
            "created_at",
            "updated_at",
        ]


class ChildWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChildWallet
        fields = [
            "id",
            "balance",
            "updated_at",
        ]


class ChildTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChildTransaction
        fields = [
            "id",
            "amount",
            "transaction_type",
            "source",
            "description",
            "created_at",
        ]


class ShopPurchaseSerializer(serializers.ModelSerializer):
    item = ShopItemSerializer(read_only=True)

    class Meta:
        model = ShopPurchase
        fields = [
            "id",
            "item",
            "price_points",
            "status",
            "created_at",
        ]


class ShopPurchaseCreateSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()


class SOSAlertSerializer(serializers.ModelSerializer):
    child = ChildSerializer(read_only=True)
    parent = UserSerializer(read_only=True)

    class Meta:
        model = SOSAlert
        fields = [
            "id",
            "child",
            "parent",
            "latitude",
            "longitude",
            "address",
            "note",
            "status",
            "created_at",
            "updated_at",
        ]


class CreateSOSAlertSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        allow_null=True
    )

    longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        allow_null=True
    )

    address = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )

    note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )
    
    
class ChildInstalledAppSerializer(serializers.ModelSerializer):
    is_blocked = serializers.SerializerMethodField()
    limit = serializers.SerializerMethodField()
    today_usage_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ChildInstalledApp
        fields = [
            "id",
            "app_name",
            "package_name",
            "category",
            "is_system_app",
            "is_active",
            "is_blocked",
            "limit",
            "today_usage_seconds",
            "last_synced_at",
            "created_at",
        ]

    def get_is_blocked(self, obj):
        try:
            return obj.block.is_blocked
        except ChildBlockedApp.DoesNotExist:
            return False

    def get_limit(self, obj):
        try:
            limit = obj.limit
            return {
                "id": limit.id,
                "daily_limit_seconds": limit.daily_limit_seconds,
                "daily_limit_minutes": limit.daily_limit_minutes(),
                "is_enabled": limit.is_enabled,
            }
        except ChildAppLimit.DoesNotExist:
            return None

    def get_today_usage_seconds(self, obj):
        from django.utils import timezone

        usage_date = self.context.get("usage_date") or timezone.localdate()

        usage = ChildAppUsage.objects.filter(
            app=obj,
            usage_date=usage_date
        ).first()

        if not usage:
            return 0

        return usage.total_usage_seconds


class ChildAppSyncItemSerializer(serializers.Serializer):
    app_name = serializers.CharField(max_length=150)
    package_name = serializers.CharField(max_length=255)
    category = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    is_system_app = serializers.BooleanField(default=False)


class ChildAppSyncSerializer(serializers.Serializer):
    apps = ChildAppSyncItemSerializer(many=True)


class ChildAppUsageItemSerializer(serializers.Serializer):
    package_name = serializers.CharField(max_length=255)
    usage_date = serializers.DateField()
    total_usage_seconds = serializers.IntegerField(min_value=0)
    open_count = serializers.IntegerField(min_value=0, required=False, default=0)
    first_opened_at = serializers.DateTimeField(required=False, allow_null=True)
    last_opened_at = serializers.DateTimeField(required=False, allow_null=True)


class ChildAppUsageSyncSerializer(serializers.Serializer):
    usages = ChildAppUsageItemSerializer(many=True)


class ChildAppUsageSerializer(serializers.ModelSerializer):
    app = ChildInstalledAppSerializer(read_only=True)

    class Meta:
        model = ChildAppUsage
        fields = [
            "id",
            "app",
            "usage_date",
            "total_usage_seconds",
            "open_count",
            "first_opened_at",
            "last_opened_at",
            "updated_at",
            "created_at",
        ]


class SetChildAppLimitSerializer(serializers.Serializer):
    daily_limit_seconds = serializers.IntegerField(
        min_value=60,
        max_value=86400
    )
    is_enabled = serializers.BooleanField(default=True)


class ChildAppLimitSerializer(serializers.ModelSerializer):
    app = ChildInstalledAppSerializer(read_only=True)

    class Meta:
        model = ChildAppLimit
        fields = [
            "id",
            "app",
            "daily_limit_seconds",
            "is_enabled",
            "created_at",
            "updated_at",
        ]


class BlockChildAppSerializer(serializers.Serializer):
    is_blocked = serializers.BooleanField(default=True)
    reason = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )


class ChildBlockedAppSerializer(serializers.ModelSerializer):
    app = ChildInstalledAppSerializer(read_only=True)

    class Meta:
        model = ChildBlockedApp
        fields = [
            "id",
            "app",
            "is_blocked",
            "reason",
            "created_at",
            "updated_at",
        ]
        
        
class ChildTrackPointSerializer(serializers.ModelSerializer):
    speed_kmh = serializers.SerializerMethodField()

    class Meta:
        model = ChildLocation
        fields = [
            "id",
            "latitude",
            "longitude",
            "accuracy",
            "battery_level",
            "speed",
            "speed_kmh",
            "heading",
            "source",
            "created_at",
        ]

    def get_speed_kmh(self, obj):
        if obj.speed is None:
            return None

        # Agar Flutter speed'ni m/s yuborsa:
        return round(obj.speed * 3.6, 2)