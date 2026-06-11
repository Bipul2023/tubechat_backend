# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# gcc and libpq-dev are required for psycopg2 and potentially other Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the project into the container
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Run the application with Daphne (ASGI) for Django Channels support
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]
