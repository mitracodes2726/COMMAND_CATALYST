FROM python:3.12-slim
WORKDIR /app
COPY proxytwin ./proxytwin
COPY examples ./examples
ENV PTWIN_HOST=0.0.0.0 PTWIN_PORT=8080
EXPOSE 8080
CMD ["python", "-m", "proxytwin.server"]
