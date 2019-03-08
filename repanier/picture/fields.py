# -*- coding: utf-8 -*-
from django.core.files.storage import default_storage
from django.db.models import Field, NOT_PROVIDED
from django.db.models.fields.files import FileDescriptor, FieldFile

from repanier.picture.const import SIZE_M
from repanier.widget.picture import RepanierPictureWidget


class RepanierPictureField(Field):
    storage = default_storage
    attr_class = FieldFile
    descriptor_class = FileDescriptor

    def __init__(self, *args, **kwargs):
        upload_to = kwargs.pop('upload_to', 'pictures')
        size = kwargs.pop('size', SIZE_M)
        bootstrap = kwargs.pop('bootstrap', False)

        self.widget = RepanierPictureWidget(
            upload_to=upload_to,
            size=size,
            bootstrap=bootstrap
        )
        super(RepanierPictureField, self).__init__(*args, **kwargs)

    def contribute_to_class(self, cls, name, private_only=False, virtual_only=NOT_PROVIDED):
        super(RepanierPictureField, self).contribute_to_class(cls, name, private_only=private_only, virtual_only=virtual_only)
        setattr(cls, self.name, self.descriptor_class(self))

    def get_prep_value(self, value):
        """Returns field's value prepared for saving into a database."""
        # Need to convert File objects provided via a form to unicode for database insertion
        if value is None:
            return
        return str(value)

    def get_internal_type(self):
        return "TextField"

    def formfield(self, **kwargs):
        defaults = {'widget': self.widget}
        defaults.update(kwargs)
        return super(RepanierPictureField, self).formfield(**defaults)


class AjaxPictureField(RepanierPictureField):
    # Needed for "makemigration" of old Repanier instance
    pass
