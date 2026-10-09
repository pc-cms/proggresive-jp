FROM python:3.12-slim
WORKDIR /opt/progressive
COPY requirements.lock .
COPY .wheelhouse /opt/wheelhouse
RUN cd /opt/wheelhouse && sha256sum -c SHA256SUMS && pip install --no-cache-dir --no-index --find-links=/opt/wheelhouse -r /opt/progressive/requirements.lock && rm -rf /opt/wheelhouse
COPY app app
COPY migrations migrations
COPY web web
RUN chmod -R a+rX /opt/progressive && useradd --system --uid 10001 progressive
USER progressive
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
