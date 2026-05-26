from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from decouple import config
import requests

User = get_user_model()

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        credential = request.data.get('credential')

        if not credential:
            return Response(
                {'error': 'Google credential is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Verify the token Google sent us is genuine
            google_data = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                config('GOOGLE_CLIENT_ID'),
                clock_skew_in_seconds=10,  # Small tolerance for clock differences
            )

             # Makes sure the token is from Google
            if google_data.get('iss') not in [
                'accounts.google.com',
                'https://accounts.google.com'
            ]:
                raise ValueError('Wrong issuer.')
            
        except ValueError as e:
            return Response(
                {'error': f'Invalid Google token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = google_data.get('email')
        first_name = google_data.get('given_name', '')
        last_name = google_data.get('family_name', '')

        if not email:
            return Response(
                {'error': 'Could not retrieve email from Google.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create user — if they already have an account,
        # Google login just signs them in
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
            }
        )

        # Handle username collisions gracefully
        if created and User.objects.filter(
            username=user.username
        ).exclude(pk=user.pk).exists():
            user.username = f"{email.split('@')[0]}_{user.pk}"
            user.save()

        # Issue our JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'is_new': created,
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })