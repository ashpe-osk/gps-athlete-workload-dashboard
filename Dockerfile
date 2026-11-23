FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=80

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .streamlit .streamlit
COPY app app
COPY src src
COPY data/raw data/raw
COPY assets/fonts assets/fonts

EXPOSE 80

CMD ["sh", "-c", "python -m streamlit run app/app.py --server.address=0.0.0.0 --server.port=${PORT:-80} --server.headless=true --server.runOnSave=false"]
