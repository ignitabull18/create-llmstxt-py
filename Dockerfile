FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Copy requirements first for better caching
COPY --chown=app:app requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Add user's local bin to PATH
ENV PATH="/home/app/.local/bin:${PATH}"

# Copy application files
COPY --chown=app:app . .

# Make the script executable
RUN chmod +x generate-llmstxt.py

# Set default environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command
CMD ["python", "generate-llmstxt.py", "--help"] 