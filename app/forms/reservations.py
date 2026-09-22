from datetime import datetime, timedelta

from django import forms
from django.utils import timezone

from app.models import Space


def _time_hhmm(value) -> str:
    """Normaliza time/datetime/string para HH:MM (input type=time)."""
    if value in (None, ""):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    text = str(value).strip()
    if "T" in text:
        # "2026-09-23T08:00[:00][±offset]" → só a parte da hora
        text = text.split("T", 1)[1]
    text = text.replace("Z", "")
    for sep in ("+", "-"):
        # remove offset de fuso, se houver (ex.: 08:00:00-03:00)
        if sep in text[1:]:
            text = text.split(sep, 1)[0]
            break
    return text[:5] if len(text) >= 5 else text


def last_start_time(space: Space):
    """Último horário em que ainda cabe 1h antes do fechamento."""
    closing = datetime.combine(datetime.today().date(), space.closing_time)
    return (closing - timedelta(hours=1)).time()


class ReservationForm(forms.Form):
    """Nova reserva: data fixa do slot + início/fim editáveis no mesmo dia."""

    date = forms.DateField(
        label="Data",
        input_formats=["%Y-%m-%d"],
        widget=forms.HiddenInput,
        error_messages={
            "required": "Informe a data.",
            "invalid": "Informe uma data válida.",
        },
    )
    start_time = forms.TimeField(
        label="Início",
        input_formats=["%H:%M", "%H:%M:%S"],
        error_messages={
            "required": "Informe o início.",
            "invalid": "Informe um horário de início válido.",
        },
    )
    end_time = forms.TimeField(
        label="Fim",
        input_formats=["%H:%M", "%H:%M:%S"],
        error_messages={
            "required": "Informe o fim.",
            "invalid": "Informe um horário de fim válido.",
        },
    )
    guests_count = forms.IntegerField(
        label="Quantidade de pessoas",
        min_value=1,
        error_messages={
            "required": "Informe a quantidade de pessoas.",
            "invalid": "Informe um número válido de pessoas.",
            "min_value": "Informe ao menos 1 pessoa.",
        },
    )
    notes = forms.CharField(
        label="Observações",
        required=False,
        widget=forms.Textarea,
    )

    def __init__(self, *args, space: Space, locked_date=None, **kwargs):
        self.space = space
        self.locked_date = locked_date
        super().__init__(*args, **kwargs)
        self.fields["guests_count"].widget.attrs["max"] = space.capacity

        opening = _time_hhmm(space.opening_time)
        closing = _time_hhmm(space.closing_time)
        max_start = _time_hhmm(last_start_time(space))

        start_value = self["start_time"].value()
        if start_value not in (None, ""):
            start_clock = (
                start_value
                if hasattr(start_value, "strftime")
                else datetime.strptime(_time_hhmm(start_value), "%H:%M").time()
            )
            end_min_dt = datetime.combine(datetime.today().date(), start_clock) + timedelta(
                hours=1
            )
            end_min = _time_hhmm(end_min_dt.time())
        else:
            end_min_dt = datetime.combine(
                datetime.today().date(), space.opening_time
            ) + timedelta(hours=1)
            end_min = _time_hhmm(end_min_dt.time())

        self.start_min = opening
        self.start_max = max_start
        self.end_min = end_min
        self.end_max = closing
        self.fields["start_time"].widget.attrs.update(
            {
                "type": "time",
                "step": "3600",
                "min": opening,
                "max": max_start,
            }
        )
        self.fields["end_time"].widget.attrs.update(
            {
                "type": "time",
                "step": "3600",
                "min": end_min,
                "max": closing,
            }
        )

    def clean_guests_count(self):
        count = self.cleaned_data["guests_count"]
        if count > self.space.capacity:
            raise forms.ValidationError(
                "A quantidade de pessoas não pode passar de "
                f"{self.space.capacity} (capacidade do espaço)."
            )
        return count

    def clean(self):
        cleaned = super().clean()
        day = cleaned.get("date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")

        if day and self.locked_date and day != self.locked_date:
            self.add_error(
                "date",
                "A reserva deve ser no dia escolhido no calendário.",
            )

        if not (day and start_time and end_time):
            return cleaned

        if end_time <= start_time:
            self.add_error(
                "end_time",
                "O horário de término deve ser posterior ao início.",
            )
            return cleaned

        tz = timezone.get_current_timezone()
        start_at = timezone.make_aware(datetime.combine(day, start_time), tz)
        end_at = timezone.make_aware(datetime.combine(day, end_time), tz)

        if start_at.date() != end_at.date():
            self.add_error(None, "A reserva não pode cruzar a meia-noite.")
            return cleaned

        opening = self.space.opening_time
        closing = self.space.closing_time
        if start_time < opening or end_time > closing:
            self.add_error(
                None,
                "Horário fora do funcionamento do espaço "
                f"({opening.strftime('%H:%M')} às {closing.strftime('%H:%M')}, "
                "no mesmo dia).",
            )
            return cleaned

        if start_at <= timezone.now():
            self.add_error("start_time", "O início deve ser no futuro.")

        cleaned["start_at"] = start_at
        cleaned["end_at"] = end_at
        return cleaned

    def time_input(self, field_name: str) -> str:
        return _time_hhmm(self[field_name].value())

    @property
    def start_input(self) -> str:
        return self.time_input("start_time")

    @property
    def end_input(self) -> str:
        return self.time_input("end_time")

    @property
    def date_iso(self) -> str:
        value = self["date"].value()
        if value in (None, ""):
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)[:10]

    @property
    def date_display(self) -> str:
        value = self["date"].value()
        if value in (None, ""):
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        text = str(value).strip()
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return text


class RescheduleForm(ReservationForm):
    """Mesmos campos da criação; o POST da view chama reschedule_reservation."""

    pass
