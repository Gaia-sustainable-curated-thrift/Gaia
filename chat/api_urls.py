from rest_framework.routers import DefaultRouter

from .api_views import ConversationViewSet

router = DefaultRouter()
router.register('conversations', ConversationViewSet, basename='api-chat-conversation')

urlpatterns = router.urls
