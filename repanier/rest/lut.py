from django.http import HttpResponse
from django.utils import translation
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers

from repanier.models import LUT_DepartmentForCustomer
from repanier.rest.view import JSONResponse


class DepartmentForCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LUT_DepartmentForCustomer
        fields = ('short_name',)


@csrf_exempt
def departments_for_customers_rest(request):
    """
    List all code snippets, or create a new snippet.
    """
    if request.method == 'GET':
        departments = LUT_DepartmentForCustomer.objects.filter(is_active=True)
        serializer = DepartmentForCustomerSerializer(departments, many=True)
        return JSONResponse(serializer.data)
    return HttpResponse(status=400)


@csrf_exempt
def department_for_customer_rest(request, short_name):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == 'GET':
        department = LUT_DepartmentForCustomer.objects.filter(
            translations__short_name=short_name.decode('unicode-escape'),
            translations__language_code=translation.get_language(),
            is_active=True
        ).order_by('?').first()
        if department is not None:
            serializer = DepartmentForCustomerSerializer(department)
            return JSONResponse(serializer.data)
    return HttpResponse(status=404)
