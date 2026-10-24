from django.contrib import messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from repanier.const import EMPTY_STRING


def import_xslx_view(
    admin_ui,
    admin,
    request,
    obj,
    sub_title,
    handle_uploaded_file,
    action,
    form_klass,
):
    """
    View for handling Excel file uploads in Django admin.

    Displays a form for uploading Excel files and processes the upload
    using the provided handle_uploaded_file function.

    Args:
        admin_ui: Django admin interface instance.
        admin: Admin model instance.
        request: Django HTTP request object.
        obj: Object being edited in the admin.
        sub_title: Subtitle for the upload form.
        handle_uploaded_file: Function to process the uploaded file.
            Signature: (request, obj, file_to_import, producer, invoice_reference) -> (error, error_msg)
        action: Admin action name.
        form_klass: Form class for the upload form.

    Returns:
        HttpResponseRedirect: Redirects to the current path after processing.
    """
    if "apply" in request.POST:
        form = form_klass(request.POST, request.FILES)
        if form.is_valid():
            file_to_import = request.FILES["file_to_import"]
            # Accept both .xlsx and .xls extensions
            if ((".xlsx" in file_to_import.name) or (".xls" in file_to_import.name)) and (file_to_import.size <= 1000000):
                producer = form.cleaned_data.get("producer")
                invoice_reference = form.cleaned_data.get(
                    "invoice_reference", EMPTY_STRING
                )
                error, error_msg = handle_uploaded_file(
                    request, obj, file_to_import, producer, invoice_reference
                )
                if error:
                    if error_msg is None:
                        admin_ui.message_user(
                            request,
                            _("Error when importing {} : Content not valid.").format(
                                file_to_import.name
                            ),
                            level=messages.WARNING,
                        )
                    else:
                        admin_ui.message_user(
                            request,
                            _("Error when importing %(file_name)s : %(error_msg)s")
                            % {
                                "file_name": file_to_import.name,
                                "error_msg": error_msg,
                            },
                            level=messages.ERROR,
                        )
                else:
                    admin_ui.message_user(
                        request,
                        _("Successfully imported {}.").format(file_to_import.name),
                    )
                    full_path = request.get_full_path()
                    split_path = full_path.split("/")
                    if len(split_path) > 5:
                        return HttpResponseRedirect("/".join(split_path[:5]))
                    return HttpResponseRedirect(full_path)
            else:
                admin_ui.message_user(
                    request,
                    _(
                        "Error when importing {} : File size must be <= 1 Mb and extension must be .xlsx or .xls"
                    ).format(file_to_import.name),
                    level=messages.ERROR,
                )
        else:
            admin_ui.message_user(
                request, _("No file to import."), level=messages.WARNING
            )
        return HttpResponseRedirect(request.get_full_path())
    form = form_klass(
        initial={"_selected_action": request.POST.getlist(ACTION_CHECKBOX_NAME)}
    )
    return render(
        request,
        form.template,
        {
            "sub_title": sub_title,
            "object": obj,
            "form": form,
            "action": action,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
        },
    )
