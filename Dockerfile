
FROM python:3.11-slim

WORKDIR /app

# Install Flask and its dependencies
RUN pip install --no-cache-dir Flask Werkzeug click

# Copy application files
COPY . .

# Flask runs on port 5000
EXPOSE 5000

# Start the application
CMD ["python", "app.py"]
