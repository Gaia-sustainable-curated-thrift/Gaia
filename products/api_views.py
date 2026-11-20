from rest_framework import permissions, viewsets

from .models import Product
from .serializers import ProductSerializer


class IsSellerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.seller_id == request.user.id


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsSellerOrReadOnly)
    queryset = (
        Product.objects.filter(status=Product.Status.AVAILABLE)
        .select_related('category', 'seller')
        .prefetch_related('images')
    )

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete()
