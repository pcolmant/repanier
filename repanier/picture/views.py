import os

from PIL import Image
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse, JsonResponse
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from repanier.tools import sint
from .const import SIZE_XS, SIZE_S, SIZE_M, SIZE_L
from .forms import FileForm


@require_POST
# @login_required
@csrf_protect
def ajax_picture(request, upload_to=None, form_class=FileForm, size=SIZE_XS):
    form = form_class(request.POST, request.FILES)
    if form.is_valid():
        size = sint(size)
        if size not in [SIZE_XS, SIZE_S, SIZE_M, SIZE_L]:
            msg = "{}".format(_("Wrong picture size."))
            return JsonResponse({"error": msg}, status=403)

        disk = os.statvfs(settings.MEDIA_ROOT)
        if disk.f_blocks > 0 and ((disk.f_bfree + 1.0) / disk.f_blocks) < 0.2:
            msg = "{}".format(
                _(
                    "Please, contact the administrator of the webserver : There is not enough disk space."
                )
            )
            return JsonResponse({"error": msg}, status=403)
        file_ = form.cleaned_data["file"]

        image_types = [
            "image/png",
            "image/jpg",
            "image/jpeg",
            "image/pjpeg",
            "image/gif",
        ]

        if file_.content_type not in image_types:
            msg = "{}".format(_("The system does not recognize the format."))
            return JsonResponse({"error": msg}, status=403)

        file_name, extension = os.path.splitext(file_.name)
        safe_name = "{}{}".format(slugify(file_name), extension)
        name = os.path.join(upload_to or "tmp", safe_name)

        if default_storage.exists(name):
            msg = "{}".format(
                _(
                    "A picture with the same file name already exist. This picture will not replace it."
                )
            )
            return JsonResponse(
                {"url": default_storage.url(name), "filename": name, "msg": msg}
            )
        else:
            image = Image.open(file_)
            if image.size[0] > size or image.size[1] > size:
                msg = "{}".format(_("The file size is too big."))
                return JsonResponse({"error": msg}, status=403)
            file_name = default_storage.save(name, image.fp)
            url = default_storage.url(file_name)
            return JsonResponse({"url": url, "filename": file_name})

    return HttpResponse(status=403)
