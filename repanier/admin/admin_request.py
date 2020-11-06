import threading

from django.contrib.admin import ModelAdmin


class ModelAdminRequest(ModelAdmin):
    def __init__(self, *args, **kwargs):
        # let's define this so there's no chance of AttributeErrors
        self._request_local = threading.local()
        self._request_local.request = None
        super().__init__(*args, **kwargs)

    def get_request(self):
        return self._request_local.request

    def set_request(self, request):
        self._request_local.request = request

    def changeform_view(self, request, *args, **kwargs):
        # stash the request
        self.set_request(request)

        # call the parent view method with all the original args
        return super().changeform_view(request, *args, **kwargs)

    def add_view(self, request, *args, **kwargs):
        self.set_request(request)
        return super().add_view(request, *args, **kwargs)

    def change_view(self, request, *args, **kwargs):
        self.set_request(request)
        return super().change_view(request, *args, **kwargs)

    def changelist_view(self, request, *args, **kwargs):
        self.set_request(request)
        return super().changelist_view(request, *args, **kwargs)

    def delete_view(self, request, *args, **kwargs):
        self.set_request(request)
        return super().delete_view(request, *args, **kwargs)

    def history_view(self, request, *args, **kwargs):
        self.set_request(request)
        return super().history_view(request, *args, **kwargs)