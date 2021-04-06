from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers

from repanier_v2.models.lut import Department


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("short_name",)


@csrf_exempt
def departments_for_customers_rest(request):
    """
    List all code snippets, or create a new snippet.
    """
    if request.method == "GET":
        departments = Department.objects.filter(is_active=True)
        serializer = DepartmentSerializer(departments, many=True)
        return JsonResponse(serializer.data)
    return HttpResponse(status=400)


@csrf_exempt
def department_rest(request, short_name):
    """
    Retrieve, update or delete a code snippet.
    """
    if request.method == "GET":
        department = (
            Department.objects.filter(
                short_name=short_name.decode("unicode-escape"),
                is_active=True,
            )
            .order_by("?")
            .first()
        )
        if department is not None:
            serializer = DepartmentSerializer(department)
            return JsonResponse(serializer.data)
    return HttpResponse(status=404)
