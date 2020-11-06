from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def version_rest(request):
    if request.method == "GET":
        return JsonResponse({"version": "1"})
    return HttpResponse(status=400)
