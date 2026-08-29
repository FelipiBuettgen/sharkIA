# 🦈 SharkIA — Classificador Inteligente de NCM

Sistema que classifica produtos automaticamente no código NCM (Nomenclatura Comum do Mercosul), usado em nota fiscal e comércio exterior no Brasil. O usuário descreve um produto em linguagem natural (ex: "Monitor LG 24 polegadas LED") e o sistema retorna o código NCM mais provável, a partir da base oficial do Siscomex.

## Como funciona

1. Base oficial: a tabela NCM vigente do Siscomex é processada, cobrindo mais de 10.500 códigos classificáveis de 8 dígitos.
2. Busca semântica: a descrição do produto é transformada em embeddings (sentence-transformers, modelo multilíngue) e comparada por similaridade vetorial via FAISS contra a base de NCMs, retornando os candidatos mais prováveis.
3. Classificação por IA: os candidatos são enviados a um LLM (Groq/Llama 3.1, com fallback para Google Gemini) que decide o código final com base no contexto.
4. API: todo o fluxo é exposto via FastAPI, com rotas administrativas para gestão de classificações e cache.

## Stack

- Python (FastAPI, sentence-transformers, FAISS)
- Groq (Llama 3.1) e Google Gemini como provedores de IA, com fallback automático
- Docker para empacotamento
- CI configurado (GitHub Actions) e pipeline de deploy preparado para Railway
- Testes automatizados (test_busca.py, test_classificador.py)

## Estrutura do projeto

```
sharkIA/
├── src/
│   ├── api/              # Rotas FastAPI (classificação, administração, cache)
│   ├── classification/   # Integração com Groq/Gemini e lógica de decisão
│   ├── search/           # Embeddings e busca semântica (FAISS)
│   ├── data/              # Processamento da base oficial do Siscomex
│   └── utils/
├── data/                  # Base NCM processada
├── Dockerfile
└── requirements.txt
```

## Status

Em desenvolvimento, com pipeline de deploy preparado para Railway. Projeto pessoal para estudo aplicado de busca semântica e integração com LLMs em um problema real de classificação fiscal.
