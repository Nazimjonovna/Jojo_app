from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    SendOTPView,
    VerifyOTPView,
    ParentRegisterView,
    MeView,
    UpdateLanguageView,
    ParentChildLogoutView,
    CreatePairingCodeView,
    ChildRegisterByCodeView,
    MyChildrenView,
    SendChildLocationView,
    ChildLastLocationView,
    ChildLocationHistoryView,
    DeviceTokenView,
    DeviceLogoutView,
    ParentRouteListCreateView,
    ParentRouteDetailView,
    AssignRouteToChildView,
    ParentChildAssignmentsView,
    ChildActiveRoutesView,
    RouteAlertListView,
    SavedLocationListCreateView,
    SavedLocationDetailView,
    KidsGameCategoryListView,
    KidsGameListView,
    KidsGameDetailView,
    KidsShopCategoryListView,
    KidsShopItemListView,
    KidsShopItemDetailView,
    KidsWalletView,
    KidsTransactionListView,
    KidsShopPurchaseView,
    KidsSOSCreateView,
    ParentSOSAlertListView,
    ParentSOSAlertResolveView,
    ChildAppSyncView,
    ChildAppUsageSyncView,
    ChildAppPolicyView,
    ParentChildAppListView,
    ParentSetChildAppLimitView,
    ParentBlockChildAppView,
    ParentChildAppUsageStatsView,
)


urlpatterns = [
    # Auth / Register
    path(
        "auth/send-otp/",
        SendOTPView.as_view(),
        name="send-otp",
    ),
    path(
        "auth/verify-otp/",
        VerifyOTPView.as_view(),
        name="verify-otp",
    ),
    path(
        "auth/parent/register/",
        ParentRegisterView.as_view(),
        name="parent-register",
    ),

    # User
    path(
        "me/",
        MeView.as_view(),
        name="me",
    ),
    path(
        "me/language/",
        UpdateLanguageView.as_view(),
        name="update-language",
    ),

    # Parent / Child pairing
    path(
        "parent/pairing-code/",
        CreatePairingCodeView.as_view(),
        name="create-pairing-code",
    ),
    path(
        "parent/children/",
        MyChildrenView.as_view(),
        name="my-children",
    ),
    path(
        "child/register-by-code/",
        ChildRegisterByCodeView.as_view(),
        name="child-register-by-code",
    ),
    path(
    "parent/children/<int:child_id>/logout/",
    ParentChildLogoutView.as_view(),
    name="parent-child-logout",
    ),

    # Location
    path(
        "child/location/",
        SendChildLocationView.as_view(),
        name="send-child-location",
    ),
    path(
        "parent/children/<int:child_id>/last-location/",
        ChildLastLocationView.as_view(),
        name="child-last-location",
    ),
    path(
        "parent/children/<int:child_id>/location-history/",
        ChildLocationHistoryView.as_view(),
        name="child-location-history",
    ),

    # Device / Firebase token
    path(
        "device-token/",
        DeviceTokenView.as_view(),
        name="device-token",
    ),
    path(
        "device-token/logout/",
        DeviceLogoutView.as_view(),
        name="device-token-logout",
    ),

    # Routes
    path(
        "parent/routes/",
        ParentRouteListCreateView.as_view(),
        name="parent-routes",
    ),
    path(
        "parent/routes/<int:route_id>/",
        ParentRouteDetailView.as_view(),
        name="parent-route-detail",
    ),
    path(
        "parent/routes/assign/",
        AssignRouteToChildView.as_view(),
        name="assign-route-to-child",
    ),
    path(
        "parent/children/<int:child_id>/routes/",
        ParentChildAssignmentsView.as_view(),
        name="parent-child-routes",
    ),
    path(
        "child/routes/active/",
        ChildActiveRoutesView.as_view(),
        name="child-active-routes",
    ),

    # Route alerts
    path(
        "parent/route-alerts/",
        RouteAlertListView.as_view(),
        name="route-alerts",
    ),
    
    # JWT refresh
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),

    # Saved locations
    path(
        "parent/saved-locations/",
        SavedLocationListCreateView.as_view(),
        name="saved-location-list-create",
    ),
    path(
        "parent/saved-locations/<int:location_id>/",
        SavedLocationDetailView.as_view(),
        name="saved-location-detail",
    ),
    
    # Kids games
    path("kids/games/categories/", KidsGameCategoryListView.as_view(), name="kids-game-categories"),
    path("kids/games/", KidsGameListView.as_view(), name="kids-games"),
    path("kids/games/<int:game_id>/", KidsGameDetailView.as_view(), name="kids-game-detail"),

    # Kids shop
    path("kids/shop/categories/", KidsShopCategoryListView.as_view(), name="kids-shop-categories"),
    path("kids/shop/items/", KidsShopItemListView.as_view(), name="kids-shop-items"),
    path("kids/shop/items/<int:item_id>/", KidsShopItemDetailView.as_view(), name="kids-shop-item-detail"),
    path("kids/shop/purchase/", KidsShopPurchaseView.as_view(), name="kids-shop-purchase"),

    # Kids wallet
    path("kids/wallet/", KidsWalletView.as_view(), name="kids-wallet"),
    path("kids/transactions/", KidsTransactionListView.as_view(), name="kids-transactions"),

    # SOS
    path("kids/sos/", KidsSOSCreateView.as_view(), name="kids-sos"),
    path("parent/sos-alerts/", ParentSOSAlertListView.as_view(), name="parent-sos-alerts"),
    path("parent/sos-alerts/<int:sos_id>/resolve/", ParentSOSAlertResolveView.as_view(), name="parent-sos-resolve"),
    
    path("child/apps/sync/", ChildAppSyncView.as_view(), name="child-app-sync"),
    path("child/apps/usage/sync/", ChildAppUsageSyncView.as_view(), name="child-app-usage-sync"),
    path("child/apps/policies/", ChildAppPolicyView.as_view(), name="child-app-policies"),

    path("parent/children/<int:child_id>/apps/", ParentChildAppListView.as_view(), name="parent-child-apps"),
    path("parent/children/<int:child_id>/apps/usage/", ParentChildAppUsageStatsView.as_view(), name="parent-child-app-usage"),
    path("parent/children/<int:child_id>/apps/<int:app_id>/limit/", ParentSetChildAppLimitView.as_view(), name="parent-child-app-limit"),
    path("parent/children/<int:child_id>/apps/<int:app_id>/block/", ParentBlockChildAppView.as_view(), name="parent-child-app-block"),
    path("parent/children/<int:child_id>/location-history/",ChildLocationHistoryView.as_view(),name="child-location-history"),
]