from django.conf.urls.defaults import *
import permanence

urlpatterns = patterns('mysite.repanier.views',
	url(r'^permanence/(\d{4})/$', permanence.views.year),
	url(r'^permanence/(\d{4})/(\d{2})/$', permanence.views.month),
	url(r'^permanence/(\d{4})/(\d{2})/(\d+)/$', permanence.views.detail),
)
