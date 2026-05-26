from rest_framework import serializers
from .models import Trade

class TradeSerializer(serializers.ModelSerializer):

    duration_minutes = serializers.SerializerMethodField()
    market_display = serializers.CharField(source='get_market_display', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    screenshot_url = serializers.SerializerMethodField() 

    class Meta:
        model = Trade
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

    def get_screenshot_url(self, obj):          
        if obj.screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.screenshot.url)
            return obj.screenshot.url
        return None
    
    def get_duration_minutes(self, obj):
        if obj.entry_time and obj.exit_time:
            delta = obj.exit_time - obj.entry_time
            return round(delta.total_seconds() / 60, 1)
        return None

    def validate(self, data):
        # Can't exit before you enter (obvious but Django won't catch this)
        if data.get('exit_time') and data.get('entry_time'):
            if data['exit_time'] < data['entry_time']:
                raise serializers.ValidationError("Exit time cannot be before entry time.")

        # Must have lot_size > 0
        if data.get('lot_size') and data['lot_size'] <= 0:
            raise serializers.ValidationError("Lot size must be greater than 0.")

        return data