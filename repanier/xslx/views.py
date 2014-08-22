# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages
from django.http import HttpResponseRedirect

from repanier.views import render_response


class ImportXlsxForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    file_to_import = forms.FileField(
        label=_('File to import'),
        allow_empty_file=False
    )


def import_xslx_view(obj, admin, request, queryset, handle_uploaded_file):
    if 'apply' in request.POST:
        form = ImportXlsxForm(request.POST, request.FILES)
        if form.is_valid():
            file_to_import = request.FILES['file_to_import']
            if ('.xlsx' in file_to_import.name) and (file_to_import.size <= 1000000):
                error, error_msg = handle_uploaded_file(request, queryset, file_to_import)
                if error:
                    if error_msg == None:
                        obj.message_user(request,
                                         _("Error when importing %s : Content not valid") % (file_to_import.name),
                                         level=messages.WARNING
                        )
                    else:
                        obj.message_user(request,
                                         _("Error when importing %(file_name)s : %(error_msg)s") % {
                                         'file_name': file_to_import.name, 'error_msg': error_msg},
                                         level=messages.ERROR
                        )
                else:
                    obj.message_user(request, _("Successfully imported %s.") % (file_to_import.name))
            else:
                obj.message_user(request,
                                 _(
                                     "Error when importing %s : File size must be <= 1 Mb and extension must be .xlsx") % (
                                 file_to_import.name),
                                 level=messages.ERROR
                )
        else:
            obj.message_user(request, _("No file to import."), level=messages.WARNING)
        return HttpResponseRedirect(request.get_full_path())
    elif 'cancel' in request.POST:
        obj.message_user(request, _("Action canceled by the user."), level=messages.WARNING)
        return HttpResponseRedirect(request.get_full_path())
    form = ImportXlsxForm(
        initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)}
    )
    return render_response(request, 'repanier/import_xlsx.html', {
    'title': _("Import products"),
    'objects': queryset,
    'import_xlsx_form': form,
    })
