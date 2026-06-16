def generate_daily_tasks(profile):
    level = profile.current_level.code

    if level == "A0":
        return [
            ("xp", 10),
            ("lesson", 1),
        ]

    if level == "A1":
        return [
            ("xp", 25),
            ("lesson", 2),
        ]

    if level == "A2":
        return [
            ("xp", 50),
            ("lesson", 3),
        ]

    return [
        ("xp", 100),
        ("lesson", 5),
    ]