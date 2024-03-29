# Copyright (c) 2010-2014 openpyxl
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# @license: http://www.opensource.org/licenses/mit-license.php
# @author: see AUTHORS file

"""Constants for fixed paths in a file and xml namespace urls."""

MIN_ROW = 0
MIN_COLUMN = 0
MAX_COLUMN = 16384
MAX_ROW = 1048576

# constants
PACKAGE_PROPS = 'docProps'
PACKAGE_XL = 'xl'
PACKAGE_RELS = '_rels'
PACKAGE_THEME = PACKAGE_XL + '/' + 'theme'
PACKAGE_WORKSHEETS = PACKAGE_XL + '/' + 'worksheets'
PACKAGE_DRAWINGS = PACKAGE_XL + '/' + 'drawings'
PACKAGE_CHARTS = PACKAGE_XL + '/' + 'charts'
PACKAGE_IMAGES = PACKAGE_XL + '/' + 'media'
PACKAGE_WORKSHEET_RELS = PACKAGE_WORKSHEETS + '/' + '_rels'

ARC_CONTENT_TYPES = '[Content_Types].xml'
ARC_ROOT_RELS = PACKAGE_RELS + '/.rels'
ARC_WORKBOOK_RELS = PACKAGE_XL + '/' + PACKAGE_RELS + '/workbook.xml.rels'
ARC_CORE = PACKAGE_PROPS + '/core.xml'
ARC_APP = PACKAGE_PROPS + '/app.xml'
ARC_WORKBOOK = PACKAGE_XL + '/workbook.xml'
ARC_STYLE = PACKAGE_XL + '/styles.xml'
ARC_THEME = PACKAGE_THEME + '/theme1.xml'
ARC_SHARED_STRINGS = PACKAGE_XL + '/sharedStrings.xml'
ARC_CUSTOM_UI = 'customUI/customUI.xml'
ARC_VBA = ('xl/vba', 'xl/activeX', 'xl/drawings', 'xl/media', 'xl/ctrlProps', 'xl/worksheets/_rels', 'customUI',
           'xl/printerSettings')

# namespaces
CHART_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
COMMENTS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
VML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
SHEET_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
CHART_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/chartDrawing"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
VTYPES_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'
XPROPS_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'
COREPROPS_NS = 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
CONTYPES_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
DCORE_NS = 'http://purl.org/dc/elements/1.1/'
DCTERMS_NS = 'http://purl.org/dc/terms/'
DCTERMS_PREFIX = 'dcterms'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
XML_NS = 'http://www.w3.org/XML/1998/namespace'
SHEET_MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
CUSTOMUI_NS = 'http://schemas.microsoft.com/office/2006/relationships/ui/extensibility'

NAMESPACES = {
    'cp': COREPROPS_NS,
    'dc': DCORE_NS,
    DCTERMS_PREFIX: DCTERMS_NS,
    'dcmitype': 'http://purl.org/dc/dcmitype/',
    'xsi': XSI_NS,
    'vt': VTYPES_NS,
    'xml': XML_NS,
    'main': SHEET_MAIN_NS
}
