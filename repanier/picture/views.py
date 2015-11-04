# -*- coding: utf-8
from __future__ import unicode_literals
from const import SIZE_XS, SIZE_M, SIZE_S
from repanier.tools import sint

try:
    from StringIO import StringIO as IO
except ImportError:
    from io import BytesIO as IO
import os
import json
from PIL import Image
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.conf import settings
from django.http import HttpResponse
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as _not_lazy
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from .forms import FileForm


@require_POST
# @login_required
@csrf_protect
def ajax_picture(request, upload_to=None, form_class=FileForm, size=SIZE_XS):
    form = form_class(request.POST, request.FILES)
    if form.is_valid():
        size = sint(size)
        if size not in [SIZE_XS, SIZE_S, SIZE_M]:
            data = json.dumps({'error': _not_lazy('Wrong size.')})
            return HttpResponse(data, content_type="application/json", status=403)

        disk = os.statvfs(settings.MEDIA_ROOT)
        if disk.f_blocks > 0 and ((disk.f_bfree + 1.0) / disk.f_blocks) < 0.2:
            data = json.dumps({'error': _not_lazy(
                'Please, contact the administrator of the webserver : There is not enough disk space.')})
            return HttpResponse(data, content_type="application/json", status=403)
        file_ = form.cleaned_data['file']

        image_types = ['image/png', 'image/jpg', 'image/jpeg', 'image/pjpeg',
                       'image/gif']

        if file_.content_type not in image_types:
            data = json.dumps({'error': _not_lazy('The system does not recognize the format.')})
            return HttpResponse(data, content_type="application/json", status=403)

        file_name, extension = os.path.splitext(file_.name)
        safe_name = '{0}{1}'.format(slugify(file_name), extension)
        # name = os.path.join(upload_to or "tmp", str(request.user.id), safe_name)
        name = os.path.join(upload_to or "tmp", safe_name)

        if default_storage.exists(name):
            return HttpResponse(
                json.dumps(
                    {'url': default_storage.url(name),
                     'filename': name,
                     'msg': _not_lazy(
                         'An image with same file name already exist. Please, check the file name and rename it if necessary.')
                     }
                ), content_type="application/json")
        else:
            image = Image.open(file_)
            if image.size[0] > size or image.size[1] > size:
                return HttpResponse(json.dumps({'error': _not_lazy('Wrong size.')}), content_type="application/json", status=403)

        file_name = default_storage.save(name, image.fp)
        url = default_storage.url(file_name)

        return HttpResponse(json.dumps({'url': url, 'filename': file_name}), content_type="application/json")

    return HttpResponse(status=403)
