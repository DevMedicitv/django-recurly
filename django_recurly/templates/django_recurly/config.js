{% autoescape off %}
Recurly.config({
  subdomain: '{{ subdomain }}',
  currency: '{{ currency }}'
});
{% endautoescape %}