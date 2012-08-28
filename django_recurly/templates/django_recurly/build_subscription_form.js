{% autoescape off %}
Recurly.buildSubscriptionForm({
  target: '#recurly-container',
  planCode: '{{ subscription.plan_code }}',
  signature: '{{ signature }}',
  {% if account %}
  account: {
    username: '{{ account.username }}',
    firstName: '{{ account.first_name }}',
    lastName: '{{ account.last_name }}',
    email: '{{ account.email }}'
  }
  {% endif %}
});
{% endautoescape %}