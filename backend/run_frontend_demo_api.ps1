$env:DATABASE_URL = 'sqlite:///frontend-demo.db'
$env:REDIS_URL = 'redis://localhost:6379/0'

python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
