from django.contrib.admin import ModelAdmin
from import_export.admin import ImportExportMixin, ExportMixin
from import_export.formats.base_formats import XLSX, ODS
from parler.admin import TranslatableAdmin


class RepanierAdminTranslatableImportExport(ImportExportMixin, TranslatableAdmin):
    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLSX, ODS) if f().can_import()]

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in (XLSX, ODS) if f().can_export()]


class RepanierAdminImportExport(ImportExportMixin, ModelAdmin):
    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLSX, ODS) if f().can_import()]

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in (XLSX, ODS) if f().can_export()]


class RepanierAdminExport(ExportMixin, ModelAdmin):
    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in (XLSX, ODS) if f().can_export()]
