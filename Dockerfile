# Dockerfile otimizado para Railway
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro (cache de camadas)
COPY requirements.txt .

# Instalar dependências Python (CPU only para economizar memória)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código e dados
COPY . .

# Expor porta
EXPOSE 8000

# Variável de ambiente para porta (Railway define automaticamente)
ENV PORT=8000

# Comando de inicialização (JSON format para melhor signal handling)
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"]
