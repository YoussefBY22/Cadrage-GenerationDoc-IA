# Contexte : racine du dépôt (docker compose build api). Hors ligne : voir deploy/offline/.
FROM python:3.12.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
COPY backend/scripts/create_user.py ./scripts/create_user.py
RUN useradd --system --uid 10001 appuser && mkdir -p /data/uploads && chown -R appuser /data
USER appuser
EXPOSE 8000
# Migrations puis serveur (une seule instance : pas de course entre migrations).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
