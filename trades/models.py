from django.db import models
from django.contrib.auth.models import User

class Trade(models.Model):

    MARKET_CHOICES = [
        ('crypto', 'Crypto'),
        ('forex', 'Forex'),
        ('stocks', 'Stocks/Equities'),
        ('synthetic', 'Synthetic Indices'),
    ]

    DIRECTION_CHOICES = [
        ('long', 'Long / Buy'),
        ('short', 'Short / Sell'),
    ]

    OUTCOME_CHOICES = [
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('breakeven', 'Breakeven'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades')

    # --- Core Trade Info ---
    symbol = models.CharField(max_length=20)          # e.g. BTC/USDT, EUR/USD, Volatility 75
    market = models.CharField(max_length=20, choices=MARKET_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)

    # --- Entry & Exit ---
    entry_price = models.DecimalField(max_digits=20, decimal_places=5)
    exit_price = models.DecimalField(max_digits=20, decimal_places=5, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=5, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=5, null=True, blank=True)
    lot_size = models.DecimalField(max_digits=10, decimal_places=5)

    # --- P&L ---
    pnl = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    outcome = models.CharField(max_length=15, choices=OUTCOME_CHOICES, null=True, blank=True)

    # --- Risk Management ---
    risk_reward_ratio = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    risk_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # in USD

    # --- Strategy & Notes ---
    strategy = models.CharField(max_length=100, blank=True)   # e.g. "Breakout", "ICT SMC"
    notes = models.TextField(blank=True)
    screenshot = models.ImageField(upload_to='trade_screenshots/', null=True, blank=True)

    # --- Timestamps ---
    entry_time = models.DateTimeField()
    exit_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_time']

    def __str__(self):
        return f"{self.symbol} | {self.direction} | {self.outcome}"

    def save(self, *args, **kwargs):
        # Auto-calculate R:R if stop_loss and take_profit are provided
        if self.entry_price and self.stop_loss and self.take_profit:
            risk = abs(self.entry_price - self.stop_loss)
            reward = abs(self.take_profit - self.entry_price)
            if risk > 0:
                self.risk_reward_ratio = round(reward / risk, 2)

        # Auto-calculate outcome from P&L
        if self.pnl is not None:
            if self.pnl > 0:
                self.outcome = 'win'
            elif self.pnl < 0:
                self.outcome = 'loss'
            else:
                self.outcome = 'breakeven'

        super().save(*args, **kwargs)