FROM python:3.12-slim

WORKDIR /app

# System deps for matplotlib/duckdb wheels (kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core.py app.py query_assistant.py prompt_manager.py ./
COPY pages/ ./pages/
COPY prompts/ ./prompts/
COPY data.csv ./

EXPOSE 8501

ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

CMD ["streamlit", "run", "app.py"]
