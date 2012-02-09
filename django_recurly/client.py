from django.conf import settings

def get_client():
    from recurly import Recurly
    
    return Recurly(
        username=settings.RECURLY_USERNAME,
        password=settings.RECURLY_PASSWORD,
        subdomain=settings.RECURLY_SUBDOMAIN,
    )
