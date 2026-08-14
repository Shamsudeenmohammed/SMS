#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SMS.settings')
    os.environ.setdefault('DJANGO_RUNSERVER_HIDE_WARNING', 'true')
    if 'runserver' in sys.argv[1:2]:
        os.environ['SECURE_SSL_REDIRECT'] = 'False'
        os.environ['SESSION_COOKIE_SECURE'] = 'False'
        os.environ['CSRF_COOKIE_SECURE'] = 'False'
        os.environ['SECURE_HSTS_SECONDS'] = '0'
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
    

if __name__ == '__main__':
    main()
