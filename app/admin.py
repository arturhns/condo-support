from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from app.models import Block, Guest, Reservation, ReservationEvent, Space, User


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "role", "block", "apartment", "is_staff")
    list_filter = ("role", "is_staff", "is_active", "block")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Condomínio", {"fields": ("role", "block", "apartment")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Condomínio", {"fields": ("email", "role", "block", "apartment")}),
    )
    search_fields = ("username", "email", "apartment", "block__name", "block__code")
    autocomplete_fields = ("block",)


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "capacity",
        "opening_time",
        "closing_time",
        "min_cancel_hours",
        "is_active",
    )
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")


class GuestInline(admin.TabularInline):
    model = Guest
    extra = 0


class ReservationEventInline(admin.TabularInline):
    model = ReservationEvent
    extra = 0
    readonly_fields = ("action", "created_at", "note")
    can_delete = False


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("protocol", "space", "user", "start_at", "status")
    list_filter = ("status", "space")
    search_fields = ("protocol", "user__email", "user__username")
    autocomplete_fields = ("space", "user", "related_reservation")
    inlines = [GuestInline, ReservationEventInline]
    date_hierarchy = "start_at"


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("name", "reservation")
    search_fields = ("name", "reservation__protocol")


@admin.register(ReservationEvent)
class ReservationEventAdmin(admin.ModelAdmin):
    list_display = ("reservation", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("reservation__protocol",)
