#!/bin/sh
set -e

echo "Aguardando o PostgreSQL em ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."

until python -c "
import os, socket, sys
host = os.environ.get('POSTGRES_HOST', 'db')
port = int(os.environ.get('POSTGRES_PORT', '5432'))
try:
    with socket.create_connection((host, port), timeout=2):
        sys.exit(0)
except OSError:
    sys.exit(1)
"; do
  sleep 1
done

echo "PostgreSQL disponível."

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Em DEBUG, --reload aplica mudanças de código sem docker compose restart.
# 1 worker evita reinícios cruzados entre workers durante o reload.
case "${DEBUG}" in
  True|true|1)
    echo "Gunicorn com --reload (DEBUG=${DEBUG})."
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers 1 \
      --reload
    ;;
  *)
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers 2
    ;;
esac
