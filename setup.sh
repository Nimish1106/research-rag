#!/bin/bash

echo "=== Research RAG Setup (FREE Stack) ==="

# Create directories
echo "Creating directories..."
mkdir -p storage/{pdfs,figures,graphs}
mkdir -p backend/{db,api,ingestion,storage,llm}
mkdir -p backend/api/{routers,models}
mkdir -p backend/db/migrations

# Copy .env
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ .env created - no API keys needed!"
fi

# Start services
echo "Starting Docker services..."
docker-compose up -d postgres qdrant ollama

echo "Waiting for services to be ready..."
sleep 10

# Pull Ollama models
echo "Pulling Ollama models (this may take a while)..."
docker exec research-rag-ollama ollama pull llama3.2:3b
docker exec research-rag-ollama ollama pull llava:13b

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start backend: docker-compose up backend"
echo "  2. Upload a PDF: curl -F 'file=@paper.pdf' http://localhost:8000/api/ingest/upload"
echo ""
echo "Models ready:"
echo "  - LLM: llama3.2:3b (text generation)"
echo "  - VLM: llava:13b (vision + text)"
echo "  - Embeddings: bge-m3 (semantic search)"