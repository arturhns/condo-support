"""Views da API REST (DRF) — pacote interno do app."""

from datetime import datetime

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.api.serializers import (
    ReservationCreateSerializer,
    ReservationRescheduleSerializer,
    ReservationSerializer,
    SpaceSerializer,
)
from app.models import Reservation, Space
from app.services.availability import day_slots
from app.services.reservations import ReservationError, cancel_reservation, reschedule_reservation


class SpaceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Space.objects.filter(is_active=True).order_by("name")
        return Response(SpaceSerializer(qs, many=True).data)


class SpaceAvailabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        space = get_object_or_404(Space, slug=slug, is_active=True)
        raw = request.query_params.get("date")
        if not raw:
            return Response(
                {"detail": "Parâmetro date=YYYY-MM-DD é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            day = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Data inválida. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slots = []
        for slot in day_slots(space, day):
            local_start = timezone.localtime(slot["start"])
            local_end = timezone.localtime(slot["end"])
            slots.append(
                {
                    "start": local_start.strftime("%H:%M"),
                    "end": local_end.strftime("%H:%M"),
                    "available": not slot["occupied"],
                }
            )
        return Response({"date": day.isoformat(), "slots": slots})


class MyReservationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Reservation.objects.filter(user=request.user)
            .select_related("space")
            .prefetch_related("guests")
            .order_by("-start_at")
        )
        return Response(ReservationSerializer(qs, many=True).data)


class ReservationCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReservationCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        reservation = serializer.save()
        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


class ReservationCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)
        try:
            cancel_reservation(reservation)
        except ReservationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        reservation.refresh_from_db()
        return Response(ReservationSerializer(reservation).data)


class ReservationRescheduleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk, user=request.user)
        serializer = ReservationRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kwargs = {
            "start_at": serializer.validated_data["start_at"],
            "end_at": serializer.validated_data["end_at"],
        }
        if "guest_names" in serializer.validated_data:
            kwargs["guest_names"] = serializer.validated_data["guest_names"]
        try:
            new_reservation = reschedule_reservation(reservation, **kwargs)
        except ReservationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ReservationSerializer(new_reservation).data,
            status=status.HTTP_200_OK,
        )
