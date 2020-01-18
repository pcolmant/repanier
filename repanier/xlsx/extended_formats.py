import tablib
from import_export.formats.base_formats import TablibFormat, XLSX_IMPORT
from django.utils.six import moves
import repanier.packages.openpyxl as openpyxl_1_8_6


class XLSX_OPENPYXL_1_8_6(TablibFormat):
    TABLIB_MODULE = 'tablib.formats._xlsx'
    CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    def can_import(self):
        return XLSX_IMPORT

    def create_dataset(self, in_stream, **kwargs):
        """
        Create dataset from first sheet.
        """
        assert XLSX_IMPORT
        from io import BytesIO
        xlsx_book = openpyxl_1_8_6.load_workbook(BytesIO(in_stream))

        dataset = tablib.Dataset()
        sheet = xlsx_book.active

        dataset.headers = [cell.value for cell in sheet.rows[0]]
        for i in moves.range(1, len(sheet.rows)):
            row_values = [cell.value for cell in sheet.rows[i]]
            dataset.append(row_values)
        return dataset
