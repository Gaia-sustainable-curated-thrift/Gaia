from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .api_views import (
    EligibleReviewOrdersView, ReviewCSRFView, ReviewViewSet, SellerReviewSummaryView,
)

app_name = 'reviews_api'

router = SimpleRouter()
router.register('', ReviewViewSet, basename='review')

urlpatterns = [
    path('csrf/', ReviewCSRFView.as_view(), name='csrf'),
    path('seller/<int:seller_id>/summary/', SellerReviewSummaryView.as_view(), name='seller-summary'),
    path('seller/<int:seller_id>/eligible-orders/', EligibleReviewOrdersView.as_view(), name='eligible-orders'),
    path('', include(router.urls)),
]
