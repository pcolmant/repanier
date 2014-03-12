# -*- coding: utf-8 -*-
import cStringIO

from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _

def export_mymodel_docx(request, queryset):
	from docx import *

	response = HttpResponse(mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
	response['Content-Disposition'] = 'attachment; filename=mymodel.docx'
	# Create our properties, contenttypes, and other support files
	title    = 'Python docx demo'
	subject  = 'A practical example of making docx from Python'
	creator  = 'Mike MacCana'
	keywords = ['python', 'Office Open XML', 'Word']

	relationships = relationshiplist()
	document = newdocument()
	body = document.xpath('/w:document/w:body', namespaces=nsprefixes)[0]
	body.append(heading(u"Titre àéè§ùµ", 1))
	body.append(heading("Sous-titre 1", 2))
	body.append(paragraph("Texte"))

	points = [ 
		'Remarque 1',
		'Remarque 2',
		'Remarque 3'
	]
	for point in points:
		body.append(paragraph(point, style='ListNumber')) 

	body.append(heading("Sous-titre 2", 2))
	body.append(paragraph("Table"))
	tbl_rows = [['Id', 'Date de distribution 2', 'Status']]
	for obj in queryset:
		row = [
			str(obj.pk),
			obj.distribution_date.strftime('%Y/%m/%d'),
			obj.status,
		]
		tbl_rows.append(row)
	body.append(table(tbl_rows))
	coreprops = coreproperties(title=title, subject=subject, creator=creator,
		keywords=keywords)
	appprops = appproperties()
	# TODO PCO : Import problem -> check cross assignement into docx lib
	contenttypes = contenttypes()
	websettings = websettings()
	wordrelationships = wordrelationships(relationships)

	# Save our document
	fobj = cStringIO.StringIO()
	savedocx(document, coreprops, appprops, contenttypes, websettings,
		wordrelationships, fobj)
	a = fobj.getvalue() 
	fobj.close() 
	response.write(a) 
	return response