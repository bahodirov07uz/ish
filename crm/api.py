from crm.models import Product
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class addproductView(APIView):
    def post(self, request):
        title = request.data.get("title")
        title = request.data.get("title")
        title = request.data.get("title")
        title = request.data.get("title")
        if not title:
            return Response({"error": "title required"}, status=400)

        task = Product.objects.create(title=title)
        return Response({"id": task.id, "title": task.title}, status=201)
