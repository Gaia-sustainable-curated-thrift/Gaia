from rest_framework.routers import DefaultRouter

from .api_views import ProductViewSet

router = DefaultRouter()
router.register('', ProductViewSet, basename='api-product')

urlpatterns = router.urls
