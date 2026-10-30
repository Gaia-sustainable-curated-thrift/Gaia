from django.contrib import admin
from .models import Review, ReviewReport


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "seller", "reviewer", "rating", "is_anonymous", "created_at"]
    list_filter = ["rating", "is_anonymous", "created_at"]
    search_fields = ["title", "comment", "seller__username", "reviewer__username"]
    readonly_fields = ["created_at", "updated_at", "seller_replied_at"]


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ["id", "review", "reporter", "reason", "resolved", "created_at"]
    list_filter = ["reason", "resolved"]
    list_editable = ["resolved"]
    readonly_fields = ["created_at"]
