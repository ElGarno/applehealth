# Dockerfile für Nutrition & Fitness Tracker (Streamlit)
FROM python:3.12-slim

# Arbeitsverzeichnis
WORKDIR /app

# System-Abhängigkeiten
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY . .

# Streamlit Konfiguration
RUN mkdir -p /root/.streamlit
RUN echo '\
[server]\n\
headless = true\n\
port = 8501\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
\n\
[theme]\n\
primaryColor = "#4CAF50"\n\
backgroundColor = "#FFFFFF"\n\
secondaryBackgroundColor = "#F5F5F5"\n\
textColor = "#262730"\n\
font = "sans serif"\n\
\n\
[browser]\n\
gatherUsageStats = false\n\
' > /root/.streamlit/config.toml

# Port freigeben
EXPOSE 8501

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Startbefehl
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
