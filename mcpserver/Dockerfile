FROM python:3.11-slim

WORKDIR /demo

# Copy requirements file first to leverage caching
COPY requirements.txt .

# Install dependencies directly into the system python or via uv properly
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install nest_asyncio

# Copy application code
COPY server.py .
COPY client-sse.py .

# Expose the port the server runs on
EXPOSE 8000

# Command to run the server using python directly
CMD ["python", "server.py"]