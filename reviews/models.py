from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Review(models.Model):
    order = models.OneToOneField(
        'accounts.AccountOrder', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='seller_review',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="written_reviews",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=100)
    comment = models.TextField(max_length=2000)
    is_anonymous = models.BooleanField(default=False)
    is_friendly = models.BooleanField(default=False)
    is_responsive = models.BooleanField(default=False)
    is_trustworthy = models.BooleanField(default=False)
    helpful_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="helpful_reviews",
    )
    seller_reply = models.TextField(max_length=1000, blank=True)
    seller_replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
            models.CheckConstraint(
                condition=~models.Q(reviewer=models.F("seller")),
                name="review_cannot_target_self",
            ),
        ]

    def __str__(self):
        return f"Review #{self.pk} - {self.rating}/5"

    @property
    def is_verified_purchase(self):
        return bool(
            self.order_id and self.order.status == 'completed'
            and self.order.user_id == self.reviewer_id
            and self.order.seller_id == self.seller_id
        )


class ReviewReport(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam or misleading content"
        OFFENSIVE = "offensive", "Offensive or abusive language"
        PRIVACY = "privacy", "Contains personal information"
        OTHER = "other", "Other"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(max_length=1000, blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["review", "reporter"], name="one_report_per_reviewer")
        ]

    def __str__(self):
        return f"Report #{self.pk} for review #{self.review_id}"
