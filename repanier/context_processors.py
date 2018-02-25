# -*- coding: utf-8 -*-
from django.conf import settings

def repanier_settings(request):
 return {'BOOTSTRAP_CSS': settings.REPANIER_SETTINGS_BOOTSTRAP_CSS}