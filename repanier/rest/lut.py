from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from repanier.models.lut import LUT_DepartmentForCustomer
from rest_framework import serializers


class DepartmentForCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LUT_DepartmentForCustomer
        fields = ("short_name",)


@csrf_exempt
def departments_for_customers_rest(request):
    """
    List all code snippets, or create a new snippet.
    """
    if request.method == "GET":
        departments = LUT_DepartmentForCustomer.objects.filter(is_active=True)
        serializer = DepartmentForCustomerSerializer(departments, many=True)
        return JsonResponse(serializer.data)
    return HttpResponse(status=400)


@csrf_exempt
def department_for_customer_rest(request, short_name):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == "GET":
        department = LUT_DepartmentForCustomer.objects.filter(
            short_name_v2=short_name.decode("unicode-escape"), is_active=True
        ).first()
        if department is not None:
            serializer = DepartmentForCustomerSerializer(department)
            return JsonResponse(serializer.data)
    return HttpResponse(status=404)
