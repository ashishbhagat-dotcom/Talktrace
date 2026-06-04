from django.urls import path
from .views import SearchView, SearchFiltersView

urlpatterns = [
    path("search/", SearchView.as_view(), name="search"),
    path("search/filters/", SearchFiltersView.as_view(), name="search-filters"),
]
