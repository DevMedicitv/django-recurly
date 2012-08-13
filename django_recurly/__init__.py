from django.conf import settings
import recurly

recurly.API_KEY = settings.RECURLY_API_KEY
