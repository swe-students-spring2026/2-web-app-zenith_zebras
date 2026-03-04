# Use Python 3.11 slim (small image)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port 3000
EXPOSE 3000

# Run Flask
CMD ["python", "app.py"]