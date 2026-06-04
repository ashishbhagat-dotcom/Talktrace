from .production import *

# No SSL yet on staging
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# MinIO files served via public server IP
import os
if USE_MINIO:
    AWS_S3_CUSTOM_DOMAIN = f"{os.environ.get('SERVER_IP', 'localhost')}:9000/{AWS_STORAGE_BUCKET_NAME}"
