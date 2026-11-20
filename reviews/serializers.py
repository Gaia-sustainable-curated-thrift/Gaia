"""JSON contracts for the existing review and order models."""
from collections.abc import Mapping

from django.db import IntegrityError, transaction
from rest_framework import serializers

from accounts.models import AccountOrder
from .models import Review, ReviewReport


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()
    order = serializers.SerializerMethodField()
    helpful_count = serializers.IntegerField(read_only=True)
    has_voted = serializers.BooleanField(read_only=True)
    has_reported = serializers.BooleanField(read_only=True)
    is_owner = serializers.SerializerMethodField()
    can_reply = serializers.SerializerMethodField()
    is_verified_purchase = serializers.BooleanField(read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'order', 'reviewer', 'reviewer_name', 'seller', 'rating',
            'title', 'comment', 'is_anonymous', 'is_friendly', 'is_responsive',
            'is_trustworthy', 'helpful_count', 'has_voted', 'has_reported',
            'is_owner', 'can_reply', 'is_verified_purchase', 'seller_reply',
            'seller_replied_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_reviewer(self, obj):
        # Match the website: anonymous identities are hidden even after login.
        if obj.is_anonymous or not self.context['request'].user.is_authenticated:
            return None
        return obj.reviewer_id

    def get_reviewer_name(self, obj):
        if obj.is_anonymous:
            return 'Anonymous'
        if not self.context['request'].user.is_authenticated:
            return 'GAIA member'
        return obj.reviewer.get_full_name() or obj.reviewer.get_username()

    def get_order(self, obj):
        # A public review must not disclose a buyer's purchase identifier.
        return obj.order_id if self.get_is_owner(obj) else None

    def get_is_owner(self, obj):
        return self.context['request'].user.pk == obj.reviewer_id

    def get_can_reply(self, obj):
        return self.context['request'].user.pk == obj.seller_id


class ReviewWriteSerializer(serializers.ModelSerializer):
    # The order is the only authority for the seller; never accept an identity.
    order = serializers.IntegerField(min_value=1, write_only=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = Review
        fields = [
            'order', 'rating', 'title', 'comment', 'is_anonymous',
            'is_friendly', 'is_responsive', 'is_trustworthy',
        ]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields.pop('order')
        return fields

    def to_internal_value(self, data):
        # Reject identity spoofing and changes to immutable/server-owned fields.
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({
                key: ['This field is not writable.'] for key in sorted(unknown)
            })
        return super().to_internal_value(data)

    def create(self, validated_data):
        order_id = validated_data.pop('order')
        user = self.context['request'].user
        try:
            with transaction.atomic():
                # Recheck eligibility while holding the same order lock as the
                # website. The existing unique constraint also prevents races.
                order = AccountOrder.objects.select_for_update().filter(
                    pk=order_id, user=user,
                    status=AccountOrder.Status.COMPLETED,
                    seller__is_active=True,
                ).exclude(seller=user).first()
                if order is None or Review.objects.filter(order=order).exists():
                    raise serializers.ValidationError({
                        'order': ['This order is not eligible for a review.'],
                    })
                return Review.objects.create(
                    order=order, reviewer=user, seller_id=order.seller_id,
                    **validated_data,
                )
        except IntegrityError:
            # A concurrent request may have reviewed/deleted the order first.
            raise serializers.ValidationError({
                'order': ['This order is no longer eligible for a review.'],
            }) from None


class SellerReplySerializer(serializers.Serializer):
    reply = serializers.CharField(max_length=1000)


class ReviewReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewReport
        fields = ['reason', 'details']


class EligibleOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountOrder
        fields = ['id', 'number', 'seller', 'product', 'title', 'date', 'status']
        read_only_fields = fields


class ReviewFilterSerializer(serializers.Serializer):
    seller = serializers.IntegerField(min_value=1, required=False)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    sort = serializers.ChoiceField(
        choices=['newest', 'helpful', 'rating'], default='newest',
    )
