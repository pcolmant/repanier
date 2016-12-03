# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _


class ImportXlsxForm(forms.Form):
    # _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    file_to_import = forms.FileField(
        label=_('File to import'),
        allow_empty_file=False
    )


def import_xslx_view(admin_ui, admin, request, queryset, sub_title, handle_uploaded_file, action):
    if 'apply' in request.POST:
        form = ImportXlsxForm(request.POST, request.FILES)
        if form.is_valid():
            file_to_import = request.FILES['file_to_import']
            if ('.xlsx' in file_to_import.name) and (file_to_import.size <= 1000000):
                # error = False
                # error_msg = EMPTY_STRING
                # # for object in queryset:
                error, error_msg = handle_uploaded_file(request, queryset, file_to_import)
                # if error:
                #     break
                if error:
                    if error_msg is None:
                        admin_ui.message_user(request,
                                              _("Error when importing %s : Content not valid") % (file_to_import.name),
                                              level=messages.WARNING
                                              )
                    else:
                        admin_ui.message_user(request,
                                              _("Error when importing %(file_name)s : %(error_msg)s") % {
                                                  'file_name': file_to_import.name, 'error_msg': error_msg},
                                              level=messages.ERROR
                                              )
                else:
                    admin_ui.message_user(request, _("Successfully imported %s.") % (file_to_import.name))
                    split_path = request.get_full_path().split('/')
                    if split_path[-2] == "import_stock":
                        return HttpResponseRedirect("/".join(request.get_full_path().split('/')[:-2]))
            else:
                admin_ui.message_user(request,
                                      _(
                                          "Error when importing %s : File size must be <= 1 Mb and extension must be .xlsx") % (
                                          file_to_import.name),
                                      level=messages.ERROR
                                      )
        else:
            admin_ui.message_user(request, _("No file to import."), level=messages.WARNING)
        return HttpResponseRedirect(request.get_full_path())
    elif 'cancel' in request.POST:
        admin_ui.message_user(request, _("Action canceled by the user."), level=messages.INFO)
        return HttpResponseRedirect(request.get_full_path())
    form = ImportXlsxForm(
        initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)}
    )
    return render(request, 'repanier/import_xlsx.html', {
        'sub_title'           : sub_title,
        'queryset'            : queryset,
        'import_xlsx_form'    : form,
        'action'              : action,
        'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
    })
