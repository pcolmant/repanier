from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.contrib.sites.models import Site

class RepanierCustomBackend(ModelBackend):
	def authenticate(self, **credentials):
		user_or_none = super(RepanierCustomBackend, self).authenticate(**credentials)
		if user_or_none:
			if user_or_none.is_superuser:
				if not (user_or_none.is_active):
					user_or_none = None
			else:
				if user_or_none.userprofile.login_site_id != Site.objects.get_current().id:
					user_or_none = None
		return user_or_none

	def get_user(self, user_id):
		try:
			user_or_none = User.objects.get(pk=user_id)
			if user_or_none:
				if user_or_none.is_superuser:
					if not (user_or_none.is_active):
						user_or_none = None
				else:
					if user_or_none.userprofile.login_site_id != Site.objects.get_current().id:
						user_or_none = None
		except User.DoesNotExist:
			user_or_none = None
		return user_or_none