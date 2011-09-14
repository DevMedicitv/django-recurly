import random
import string
import iso8601
import pytz

from django.contrib.auth.models import User

def random_string(length=32):
    return ''.join(random.choice(string.letters + string.digits) for i in xrange(length))

def modelify(data, model, key_prefix=""):
    fields = set(field.name for field in model._meta.fields)
    fields.discard("id")
    
    if "user" in fields and data.get("username", None):
        data["user"] = User.objects.get(username=data["username"])
    
    for k, v in data.items():
        if isinstance(v, dict):
            data.update(modelify(v, model, key_prefix=k+"_"))
    
    out = {}
    for k, v in data.items():
        if not k.startswith(key_prefix):
            k = key_prefix + k
        
        if k in fields:
            if k.endswith("_at"):
                v = iso8601.parse_date(v).astimezone(tz=pytz.utc) if v else None
            
            out[str(k)] = v
    
    return out