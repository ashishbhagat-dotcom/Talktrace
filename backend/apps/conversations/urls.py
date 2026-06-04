from rest_framework.routers import DefaultRouter
from .views import ActionItemViewSet, ConversationViewSet

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("action-items", ActionItemViewSet, basename="actionitem")

urlpatterns = router.urls
