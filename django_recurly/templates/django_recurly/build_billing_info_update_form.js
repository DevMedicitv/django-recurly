{% autoescape off %}
Recurly.buildBillingInfoUpdateForm({
  target: '{{ target_element }}',
  accountCode: '{{ account.account_code }}'
  signature: '{{ signature }}',

});
{% endautoescape %}