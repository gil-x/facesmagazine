# For local deployment, you shall rename this file as settings_specific.py
# And get some Stripe API keys
# In production, you have to provide also:
# ALLOWED_HOSTS = ['xxx.xx', ]
# DEFAULT_FROM_EMAIL = 'xxx@xxx.x'

SECRET_KEY = "osef"

DEBUG = True

EMAIL_HOST = 'localhost'
EMAIL_USE_TLS = False
EMAIL_PORT = 1025
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

STRIPE_SECRET_KEY='Create a Stripe account to get one'
STRIPE_PUBLISHABLE_KEY='Create a Stripe account to get one'
STRIPE_WEBHOOK_SECRET = 'Create a Stripe account to get one'

DOMAIN = 'http://0.0.0.0:8000/'
