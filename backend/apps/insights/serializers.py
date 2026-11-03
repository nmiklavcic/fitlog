from datetime import date, timedelta

from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSummarySerializer
from apps.social.visibility import are_friends
from apps.workouts.models import Exercise
from apps.workouts.serializers import ExerciseBriefSerializer

from .models import BodyMetric, Challenge

MAX_CHALLENGE_DAYS = 31


class BodyMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = BodyMetric
        fields = [
            "id",
            "measured_on",
            "bodyweight_kg",
            "body_fat_pct",
            "waist_cm",
            "chest_cm",
            "arm_cm",
            "thigh_cm",
            "hips_cm",
            "note",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        measures = [k for k in self.Meta.fields if k.endswith(("_kg", "_cm", "_pct"))]
        if not any(attrs.get(k) is not None for k in measures) and self.instance is None:
            raise serializers.ValidationError("Enter at least one measurement.")
        return attrs


class ChallengeSerializer(serializers.ModelSerializer):
    creator = UserSummarySerializer(read_only=True)
    opponent = UserSummarySerializer(read_only=True)
    opponent_username = serializers.CharField(write_only=True)
    exercise = ExerciseBriefSerializer(read_only=True)
    exercise_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    scores = serializers.SerializerMethodField()
    winner_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Challenge
        fields = [
            "id",
            "creator",
            "opponent",
            "opponent_username",
            "metric",
            "exercise",
            "exercise_id",
            "starts_on",
            "ends_on",
            "status",
            "winner_id",
            "scores",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def get_scores(self, challenge):
        from .services import challenge_score

        if challenge.status in (Challenge.Status.PENDING, Challenge.Status.DECLINED):
            return None
        return {
            "creator": challenge_score(challenge, challenge.creator),
            "opponent": challenge_score(challenge, challenge.opponent),
        }

    def validate(self, attrs):
        user = self.context["request"].user
        opponent = User.objects.filter(username__iexact=attrs.pop("opponent_username"), is_active=True).first()
        if opponent is None or not are_friends(user.pk, opponent.pk):
            raise serializers.ValidationError({"opponent_username": "You can only challenge your friends."})
        attrs["opponent"] = opponent

        if attrs["starts_on"] < date.today():
            raise serializers.ValidationError({"starts_on": "Challenges can't start in the past."})
        if attrs["ends_on"] < attrs["starts_on"] or attrs["ends_on"] - attrs["starts_on"] > timedelta(days=MAX_CHALLENGE_DAYS - 1):
            raise serializers.ValidationError({"ends_on": f"A challenge lasts 1 to {MAX_CHALLENGE_DAYS} days."})

        exercise_id = attrs.pop("exercise_id", None)
        if attrs["metric"] == Challenge.Metric.EXERCISE_VOLUME:
            # Catalogue exercises only: the opponent can't log someone else's custom exercise.
            exercise = Exercise.objects.filter(pk=exercise_id, owner__isnull=True).first()
            if exercise is None:
                raise serializers.ValidationError({"exercise_id": "Pick an exercise from the catalogue."})
            attrs["exercise"] = exercise
        return attrs
