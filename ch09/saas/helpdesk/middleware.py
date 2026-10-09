from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404

from . import tenant
from .models import Member, Organization


def subdomain(host: str):
    """The tenant's slug taken from the host name; None on the main domain."""
    name = host.split(":")[0].lower()
    base = settings.BASE_DOMAIN
    if name == base or not name.endswith("." + base):
        return None
    return name[: -(len(base) + 1)]


class TenantMiddleware:
    """From the subdomain to the organization, for the whole duration of the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.member = None
        slug = subdomain(request.get_host())
        with tenant.tenant() as context:
            if slug is not None:
                try:
                    organization = Organization.objects.get(slug=slug)
                except Organization.DoesNotExist:
                    raise Http404("Unknown organization") from None
                context.organization = request.organization = organization
                if request.user.is_authenticated:
                    try:
                        request.member = Member.objects.select_related("user").get(
                            user=request.user, organization=organization
                        )
                    except Member.DoesNotExist:
                        raise PermissionDenied("You are not a member of this organization") from None
            return self.get_response(request)
