from urllib import request

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Trade
from .serializers import TradeSerializer
from django.db.models import Sum, Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_datetime
from datetime import datetime
import time

class TradeViewSet(viewsets.ModelViewSet):
    serializer_class = TradeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['market', 'outcome', 'strategy', 'direction']
    search_fields = ['symbol', 'strategy', 'notes']
    ordering_fields = ['entry_time', 'pnl', 'risk_reward_ratio']
    ordering = ['-entry_time']

    def get_queryset(self):
        # Users only see THEIR trades — important!
        return Trade.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Auto-attach logged-in user to every trade
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Quick stats endpoint — /api/trades/summary/
        Used by the dashboard cards
        """
        queryset = self.get_queryset()

        total = queryset.count()
        wins = queryset.filter(outcome='win').count()
        losses = queryset.filter(outcome='loss').count()
        breakevens = queryset.filter(outcome='breakeven').count()

        total_pnl = sum(t.pnl for t in queryset if t.pnl is not None)
        avg_rr = queryset.exclude(risk_reward_ratio=None) \
                         .values_list('risk_reward_ratio', flat=True)
        avg_rr_value = round(sum(avg_rr) / len(avg_rr), 2) if avg_rr else 0

        win_rate = round((wins / total) * 100, 1) if total > 0 else 0

        return Response({
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'breakevens': breakevens,
            'win_rate': win_rate,
            'total_pnl': float(total_pnl),
            'avg_risk_reward': avg_rr_value,
        })
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """
        /api/trades/analytics/
        Powers the analytics page charts
        """
        queryset = self.get_queryset().exclude(pnl=None)

        # --- P&L over time ---
        pnl_over_time = (
            queryset
            .annotate(date=TruncDate('entry_time'))
            .values('date')
            .annotate(daily_pnl=Sum('pnl'))
            .order_by('date')
        )

        # Running cumulative P&L
        cumulative = 0
        pnl_chart = []
        for entry in pnl_over_time:
            cumulative += float(entry['daily_pnl'])
            pnl_chart.append({
                'date': entry['date'].strftime('%b %d'),
                'daily': float(entry['daily_pnl']),
                'cumulative': round(cumulative, 2),
            })

        # --- By market ---
        by_market = (
            queryset
            .values('market')
            .annotate(
                total=Count('id'),
                wins=Count('id', filter=Q(outcome='win')),
                losses=Count('id', filter=Q(outcome='loss')),
                total_pnl=Sum('pnl'),
            )
            .order_by('market')
        )

        # --- By strategy ---
        by_strategy = (
            queryset
            .exclude(strategy='')
            .values('strategy')
            .annotate(
                total=Count('id'),
                wins=Count('id', filter=Q(outcome='win')),
                total_pnl=Sum('pnl'),
                avg_rr=Avg('risk_reward_ratio'),
            )
            .order_by('-total_pnl')
        )

        # --- Outcome breakdown ---
        outcome_data = [
            {'name': 'Wins', 'value': queryset.filter(outcome='win').count()},
            {'name': 'Losses', 'value': queryset.filter(outcome='loss').count()},
            {'name': 'Breakeven', 'value': queryset.filter(outcome='breakeven').count()},
        ]

        return Response({
            'pnl_over_time': pnl_chart,
            'by_market': list(by_market),
            'by_strategy': list(by_strategy),
            'outcome_breakdown': outcome_data,
        })
    
    @action(detail=False, methods=['post'], url_path='import_csv')
    def import_csv(self, request):
        """
        POST /api/trades/import_csv/
        Multipart form with 'file' field containing CSV
        """
        from .csv_import import parse_csv_trades

        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file uploaded. Send a CSV file in the "file" field.'},
                status=400
            )

        uploaded_file = request.FILES['file']

        # Validate file type
        if not uploaded_file.name.endswith('.csv'):
            return Response(
                {'error': 'Only CSV files are supported.'},
                status=400
            )

        # 5MB max
        if uploaded_file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'File too large. Maximum size is 5MB.'},
                status=400
            )

        result = parse_csv_trades(uploaded_file, request.user)

        if 'error' in result:
            return Response(result, status=400)

        return Response(result)   

    @action(detail=True, methods=['post'], url_path='upload_screenshot')
    def upload_screenshot(self, request, pk=None):
        """
        POST /api/trades/{id}/upload_screenshot/
        Multipart form with 'screenshot' field
        """
        trade = self.get_object()

        if 'screenshot' not in request.FILES:
            return Response(
                {'error': 'No file uploaded.'},
                status=400
            )

        file = request.FILES['screenshot']

        # Validate image type
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
        if file.content_type not in allowed_types:
            return Response(
                {'error': 'Only JPEG, PNG, WebP and GIF images are supported.'},
                status=400
            )

        # 10MB max for screenshots
        if file.size > 10 * 1024 * 1024:
            return Response(
                {'error': 'Image too large. Maximum size is 10MB.'},
                status=400
            )

        # Delete old screenshot if exists
        if trade.screenshot:
            trade.screenshot.delete(save=False)

        trade.screenshot = file
        trade.save()

        return Response({
            'screenshot': request.build_absolute_uri(trade.screenshot.url)
        }) 