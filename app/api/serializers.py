"""Serializers da API REST (DRF) — pacote interno do app."""

from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from app.models import Reservation, Space
from app.services.availability import is_within_operating_hours
from app.services.reservations import ReservationError, create_reservation


class SpaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Space
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "capacity",
            "opening_time",
            "closing_time",
            "min_cancel_hours",
        )


class ReservationSerializer(serializers.ModelSerializer):
    space = SpaceSerializer(read_only=True)
    space_slug = serializers.SlugField(source="space.slug", read_only=True)
    guest_names = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = (
            "id",
            "protocol",
            "space",
            "space_slug",
            "start_at",
            "end_at",
            "status",
            "notes",
            "guests_count",
            "guest_names",
            "created_at",
        )

    def get_guest_names(self, obj):
        return list(obj.guests.values_list("name", flat=True))


class ReservationCreateSerializer(serializers.Serializer):
    space = serializers.SlugField()
    date = serializers.DateField(input_formats=["%Y-%m-%d"])
    start_time = serializers.TimeField(input_formats=["%H:%M", "%H:%M:%S"])
    end_time = serializers.TimeField(input_formats=["%H:%M", "%H:%M:%S"])
    guest_names = serializers.ListField(
        child=serializers.CharField(max_length=120, allow_blank=True),
        required=False,
        default=list,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_space(self, value):
        try:
            return Space.objects.get(slug=value, is_active=True)
        except Space.DoesNotExist as exc:
            raise serializers.ValidationError("Espaço não encontrado.") from exc

    def validate(self, attrs):
        space = attrs["space"]
        day = attrs["date"]
        start_at = timezone.make_aware(datetime.combine(day, attrs["start_time"]))
        end_at = timezone.make_aware(datetime.combine(day, attrs["end_time"]))
        if end_at <= start_at:
            raise serializers.ValidationError(
                {"end_time": "O horário de término deve ser posterior ao início."}
            )
        if not is_within_operating_hours(space, start_at, end_at):
            opening = space.opening_time.strftime("%H:%M")
            closing = space.closing_time.strftime("%H:%M")
            raise serializers.ValidationError(
                f"Horário fora do funcionamento do espaço ({opening} às {closing})."
            )
        attrs["start_at"] = start_at
        attrs["end_at"] = end_at
        return attrs

    def create(self, validated_data):
        names = validated_data.get("guest_names") or []
        try:
            return create_reservation(
                space=validated_data["space"],
                user=self.context["request"].user,
                start_at=validated_data["start_at"],
                end_at=validated_data["end_at"],
                notes=validated_data.get("notes") or "",
                guest_names=names,
                guests_count=len([n for n in names if n and str(n).strip()]),
            )
        except ReservationError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class ReservationRescheduleSerializer(serializers.Serializer):
    date = serializers.DateField(input_formats=["%Y-%m-%d"])
    start_time = serializers.TimeField(input_formats=["%H:%M", "%H:%M:%S"])
    end_time = serializers.TimeField(input_formats=["%H:%M", "%H:%M:%S"])
    guest_names = serializers.ListField(
        child=serializers.CharField(max_length=120, allow_blank=True),
        required=False,
    )

    def validate(self, attrs):
        day = attrs["date"]
        start_at = timezone.make_aware(datetime.combine(day, attrs["start_time"]))
        end_at = timezone.make_aware(datetime.combine(day, attrs["end_time"]))
        if end_at <= start_at:
            raise serializers.ValidationError(
                {"end_time": "O horário de término deve ser posterior ao início."}
            )
        attrs["start_at"] = start_at
        attrs["end_at"] = end_at
        return attrs
