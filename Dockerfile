FROM python:3.12-alpine
RUN pip install --upgrade pip
ENV PYTHONUNBUFFERED=1
WORKDIR /gfs
RUN mkdir -p /data
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]