"""DRF endpoints kept separate from the existing HTML views."""
from django.db import transaction
from django.db.models import Avg, BooleanField, Count, Exists, OuterRef, Value
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Review, ReviewReport
from .purchases import eligible_orders
from .serializers import (
    EligibleOrderSerializer, ReviewFilterSerializer, ReviewReportSerializer,
    ReviewSerializer, ReviewWriteSerializer, SellerReplySerializer,
)
from .views import _get_seller


class ReviewPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'page_size'
    max_page_size = 100


class ReviewAPI:
    authentication_classes = [SessionAuthentication]
    renderer_classes = [JSONRenderer]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # Identities and ownership flags depend on the requesting user.
        response['Cache-Control'] = 'private, no-store'
        return response


class ReviewViewSet(ReviewAPI, viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = ReviewPagination
    lookup_value_regex = r'\d+'

    def get_queryset(self):
        queryset = Review.objects.select_related('reviewer', 'seller', 'order').annotate(
            helpful_count=Count('helpful_by', distinct=True),
        )
        user = self.request.user
        if user.is_authenticated:
            queryset = queryset.annotate(
                has_voted=Exists(Review.helpful_by.through.objects.filter(
                    review_id=OuterRef('pk'), user_id=user.pk,
                )),
                has_reported=Exists(ReviewReport.objects.filter(
                    review_id=OuterRef('pk'), reporter=user,
                )),
            )
        else:
            queryset = queryset.annotate(
                has_voted=Value(False, output_field=BooleanField()),
                has_reported=Value(False, output_field=BooleanField()),
            )
        # Query filters apply only to collections, never object permissions.
        if self.action in ['list', 'mine', 'seller_reviews']:
            params = ReviewFilterSerializer(data=self.request.query_params)
            params.is_valid(raise_exception=True)
            filters = params.validated_data
            if 'seller_id' in self.kwargs:
                queryset = queryset.filter(seller=_get_seller(self.kwargs['seller_id']))
            elif 'seller' in filters:
                queryset = queryset.filter(seller=_get_seller(filters['seller']))
            if self.action == 'mine':
                queryset = queryset.filter(reviewer=user)
            if 'rating' in filters:
                queryset = queryset.filter(rating=filters['rating'])
            orderings = {
                'newest': ['-created_at', '-pk'],
                'helpful': ['-helpful_count', '-created_at', '-pk'],
                'rating': ['-rating', '-created_at', '-pk'],
            }
            queryset = queryset.order_by(*orderings[filters['sort']])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = ReviewWriteSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response(self.get_serializer(self.get_queryset().get(pk=review.pk)).data,
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        review = self.get_object()
        self.require_author(review)
        serializer = ReviewWriteSerializer(
            review, data=request.data, partial=kwargs.pop('partial', False),
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self.get_serializer(review).data)

    def perform_destroy(self, instance):
        self.require_author(instance)
        instance.delete()

    def require_author(self, review):
        if review.reviewer_id != self.request.user.pk:
            raise PermissionDenied('Only the author can edit or delete this review.')

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mine(self, request):
        return self.list(request)

    @action(detail=False, methods=['get'], url_path=r'seller/(?P<seller_id>\d+)')
    def seller_reviews(self, request, seller_id=None):
        return self.list(request)

    @action(detail=True, methods=['post'])
    def helpful(self, request, pk=None):
        with transaction.atomic():
            review = get_object_or_404(Review.objects.select_for_update(), pk=pk)
            if request.user.pk in [review.reviewer_id, review.seller_id]:
                raise PermissionDenied("You cannot vote on your own review or your store's review.")
            vote, created = Review.helpful_by.through.objects.get_or_create(
                review_id=review.pk, user_id=request.user.pk,
            )
            if not created:
                vote.delete()
            count = review.helpful_by.count()
        return Response({'has_voted': created, 'helpful_count': count})

    @action(detail=True, methods=['post', 'delete'])
    def reply(self, request, pk=None):
        review = self.get_object()
        if review.seller_id != request.user.pk:
            raise PermissionDenied('Only the reviewed seller can manage this reply.')
        if request.method == 'DELETE':
            review.seller_reply = ''
            review.seller_replied_at = None
        else:
            serializer = SellerReplySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            review.seller_reply = serializer.validated_data['reply']
            review.seller_replied_at = timezone.now()
        review.save(update_fields=['seller_reply', 'seller_replied_at'])
        return Response(self.get_serializer(review).data)

    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        review = self.get_object()
        if review.reviewer_id == request.user.pk:
            raise PermissionDenied('You cannot report your own review.')
        serializer = ReviewReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, created = ReviewReport.objects.get_or_create(
            review=review, reporter=request.user, defaults=serializer.validated_data,
        )
        return Response({'has_reported': True},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class SellerReviewSummaryView(ReviewAPI, APIView):
    permission_classes = [AllowAny]

    def get(self, request, seller_id):
        seller = _get_seller(seller_id)
        reviews = Review.objects.filter(seller=seller)
        summary = reviews.aggregate(average_rating=Avg('rating'), total_reviews=Count('pk'))
        counts = dict(reviews.order_by().values_list('rating').annotate(count=Count('pk')))
        total = summary['total_reviews']
        return Response({
            'seller': seller.pk, **summary,
            'rating_breakdown': [
                {'rating': rating, 'count': counts.get(rating, 0),
                 'percent': round(counts.get(rating, 0) * 100 / total) if total else 0}
                for rating in range(5, 0, -1)
            ],
        })


class EligibleReviewOrdersView(ReviewAPI, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EligibleOrderSerializer
    pagination_class = ReviewPagination

    def get_queryset(self):
        seller = _get_seller(self.kwargs['seller_id'])
        return eligible_orders(self.request.user, seller)


class ReviewCSRFView(ReviewAPI, APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'csrfToken': get_token(request)})
