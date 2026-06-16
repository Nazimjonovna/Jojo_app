from jojolingo.models import ChildTopicStat


def register_topic_interaction(
    profile,
    lesson,
    is_correct,
    time_spent_seconds=0,
):
    topics = lesson.topics.all()

    for topic in topics:
        stat, _ = ChildTopicStat.objects.get_or_create(
            profile=profile,
            topic=topic,
        )

        stat.interactions += 1

        if is_correct:
            stat.correct_answers += 1

        stat.total_time_seconds += time_spent_seconds

        stat.save()
        
        
def detect_interests(profile):
    stats = (
        profile.topic_stats
        .order_by("-interactions")
        [:5]
    )

    profile.interests = [
        item.topic.name
        for item in stats
    ]

    profile.save(
        update_fields=["interests"]
    )

    return profile.interests