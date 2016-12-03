from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from repanier.rest.view import JSONResponse


@csrf_exempt
def version_rest(request):
    if request.method == 'GET':
        return JSONResponse({'version': '1'})
    return HttpResponse(status=400)
