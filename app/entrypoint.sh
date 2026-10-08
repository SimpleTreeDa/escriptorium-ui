#!/bin/sh


echo "Waiting for postgres..."
while ! nc -z $SQL_HOST $SQL_PORT; do
    sleep 0.1
done
echo "PostgreSQL started"

python manage.py migrate

# static files: --clear, so the static volume holds exactly what this image
# ships. Without it collectstatic keeps any file whose previously collected
# copy is newer than the source (it only compares modification times, and
# webpack leaves a bundle it did not need to rewrite with its old time), so a
# deploy could update editor.js and leave a stale editor.css behind it.
python manage.py collectstatic --no-input --clear

exec "$@"
