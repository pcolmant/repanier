# -------------------------------------------------------------------------
# http://stackoverflow.com/questions/2680902/python-django-global-variables
#
# import threading
#
# class MyModel(ModelBase):
#     _counter = 0
#     _counter_lock = threading.Lock()
#
#     @classmethod
#     def increment_counter(cls):
#         with cls._counter_lock:
#             cls._counter += 1
#
#     def some_action(self):
#         # core code
#         self.increment_counter()
#
#
# # somewhere else
# print MyModel._counter

# ----------------------------------------------------------
# https://github.com/isotoma/django-json-settings/
#
# import sys
# import os
# import logging
# import json
#
# def json_patch(path):
#     logging.warn("Attempting to load local settings from %r" %(path,))
#     try:
#         d = json.load(open(path))
#     except IOError:
#         logging.exception("Unable to open json settings in %r" % (path,))
#         raise SystemExit(-1)
#     except ValueError:
#         logging.exception("Unable to parse json settings in %r" % (path,))
#         raise SystemExit(-1)
#     for k,v in d.items():
#         globals()[k] = v
#
# def patch_settings():
#     env_settings = os.environ.get('JSON_SETTINGS', None)
#     if env_settings is None:
#         # we only use the default if it exists
#         env_settings = os.path.join(sys.prefix, "etc", "settings.json")
#         if not os.path.exists(env_settings):
#             return
#     json_patch(env_settings)
#     if not "VAR_DIRECTORY" in globals():
#         globals()["VAR_DIRECTORY"] = os.path.join(sys.prefix, "var")
#     if not "STATIC_ROOT" in globals():
#         globals()["STATIC_ROOT"] = os.path.join(globals()["VAR_DIRECTORY"],
#                                                 "static")
#     if not "MEDIA_ROOT" in globals():
#         globals()["MEDIA_ROOT"] = os.path.join(globals()["VAR_DIRECTORY"],
#                                                "media")
#
#
# patch_settings()

# ------------------------------------------------------------
# https://github.com/django-import-export/django-import-export/issues/349#issuecomment-159769077
#
# author = models.ManyToManyField(User, blank=True, editable=False)
#
# def import_data(self, *args, **kwargs):
#     self._user = kwargs.get('user', None)
#     return super(KWResource, self).import_data(*args, **kwargs)
#
# def after_save_instance(self, instance, dry_run, **kwargs):
#
#     instance.save()
#     instance.author.add(self._user)