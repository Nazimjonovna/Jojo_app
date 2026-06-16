def calculate_next_difficulty(profile):
    analytics = getattr(profile.child, "learning_analytics", None)

    if not analytics:
        return "normal"

    accuracy = analytics.average_accuracy
    avg_time = analytics.average_time_per_exercise or 0

    if accuracy >= 90 and avg_time and avg_time <= 12:
        return "hard"

    if accuracy < 65:
        return "easy"

    return "normal"


def get_difficulty_number(difficulty_label):
    if difficulty_label == "easy":
        return 1

    if difficulty_label == "hard":
        return 3

    return 2