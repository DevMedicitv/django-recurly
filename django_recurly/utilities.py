import random
import string
import iso8601
import pytz

from django.contrib.auth.models import User

def random_string(length=32):
    return ''.join(random.choice(string.letters + string.digits) for i in xrange(length))

def modelify(data, model, key_prefix="", remove_empty=False, date_fields=[]):
    fields = set(field.name for field in model._meta.fields)
    fields_by_name = dict((field.name, field) for field in model._meta.fields)
    fields.discard("id")
    
    if "user" in fields and data.get("username", None):
        try:
            data["user"] = User.objects.get(username=data["username"])
        except User.DoesNotExist:
            # A user may not exist if there account has been deleted
            data["user"] = None
    
    for k, v in data.items():
        if isinstance(v, dict):
            data.update(modelify(v, model, key_prefix=k+"_"))
    
    out = {}
    for k, v in data.items():
        if not k.startswith(key_prefix):
            k = key_prefix + k
        
        if k in fields:
            if k.endswith("_at") or k in date_fields:
                v = iso8601.parse_date(v).astimezone(tz=pytz.utc) if v else None
            
            # Always assume fields with limited choices shoudl be lower case
            if v and fields_by_name[k].choices:
                v = v.lower()
            
            if v or not remove_empty:
                out[str(k)] = v
    
    return out