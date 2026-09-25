#!/bin/sh
set -e

# Em produção (Render/Railway) usa DATABASE_URL — não há host "db".
if [ -z "${DATABASE_URL:-}" ]; then
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
else
  echo "DATABASE_URL definida; pulando wait por POSTGRES_HOST."
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
