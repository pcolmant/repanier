from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from repanier.auth_backend import RepanierAuthBackend


@login_required()
@csrf_protect
@never_cache
def logout_view(request):
    """
    Logs out the user and displays 'You are logged out' message.
    """
    logout(request)
    # pages-root is the django cms root page.
    # pages-root may be replaced by login_form to go to the login form instead of the home page
    # The reverse may be replaced by "/" to also go to the home page
    return HttpResponseRedirect(reverse('pages-root'))


@receiver(user_logged_out)
def receiver_user_logged_out(sender, request, user, **kwargs):
    RepanierAuthBackend.remove_staff_right(
        user=user
    )
