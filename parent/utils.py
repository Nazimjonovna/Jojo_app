import math


def haversine_distance_meters(lat1, lon1, lat2, lon2):
    radius = 6371000

    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))

    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius * c


def nearest_route_point_distance(latitude, longitude, route_points):
    min_distance = None
    nearest_point = None

    for point in route_points:
        distance = haversine_distance_meters(
            latitude,
            longitude,
            point.latitude,
            point.longitude,
        )

        if min_distance is None or distance < min_distance:
            min_distance = distance
            nearest_point = point

    return min_distance, nearest_point