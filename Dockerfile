
FROM python:3.11-slim

WORKDIR /app

# Linux libraries needed by WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements into Docker
COPY requirements.txt .

# Actually install the packages
RUN python -m pip install --no-cache-dir -r requirements.txt
# Install Flask and its dependencies
RUN pip install --no-cache-dir Flask Werkzeug click

# Copy application files
COPY . .

# Flask runs on port 5000
EXPOSE 5000

# Start the application
CMD ["python", "app.py"]
