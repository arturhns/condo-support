from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from app.models import Space


@login_required
def space_list(request):
    spaces = Space.objects.filter(is_active=True)
    return render(request, "spaces/list.html", {"spaces": spaces})


@login_required
def space_detail(request, slug):
    space = get_object_or_404(Space, slug=slug, is_active=True)
    return render(request, "spaces/detail.html", {"space": space})
