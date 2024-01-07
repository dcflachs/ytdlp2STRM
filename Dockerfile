FROM python:3.9-slim
COPY requirements.txt /
RUN pip install --no-cache-dir --upgrade -r /requirements.txt
RUN pip install --no-cache-dir streamlink
WORKDIR /opt/ytdlp2STRM
COPY . /opt/ytdlp2STRM
CMD ["python", "main.py"]