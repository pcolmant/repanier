from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.conf import settings


class ContactForm(forms.Form):
    email = forms.EmailField(label='Your Email')
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'contact_form'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'
        self.helper.add_input(Submit('submit', 'Submit'))


class ContactFormAjax(forms.Form):
    email = forms.EmailField(label='Your Email')
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super(ContactFormAjax, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'contact_form_ajax'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'
        self.helper.add_input(Submit('submit', 'Submit'))
