# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy requirements and source code
COPY . /app

# Install dependencies
RUN pip install python-multipart
RUN pip install --no-cache-dir fastapi uvicorn requests python-dotenv

# Expose port 8000 for FastAPI
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
