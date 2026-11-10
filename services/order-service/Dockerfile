#FROM python:3.12-slim
FROM docker.arvancloud.ir/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .


#RUN #pip install \
#    --index-url https://mirror-pypi.runflare.com/simple/ \
#    --trusted-host mirror-pypi.runflare.com \
#    -r requirements.txt

RUN python -m pip install \
    --timeout 120 \
    --retries 5 \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

COPY . .

EXPOSE 8003

CMD ["sh", "-c", "python manage.py makemigrations && python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8003 --workers 3"]