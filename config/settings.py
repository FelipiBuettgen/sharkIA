"""
Configurações do projeto SharkIA
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Diretórios
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TABELA_DIR = BASE_DIR / "Tabela"

# Arquivos
NCM_JSON_PATH = TABELA_DIR / "Tabela_NCM_Vigente.json"
NCM_PROCESSADO_PATH = DATA_DIR / "ncm_processado.json"
NCM_ENRIQUECIDO_PATH = DATA_DIR / "ncm_enriquecido.json"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
FAISS_INDEX_PATH = DATA_DIR / "faiss.index"

# Modelo de embeddings
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384

# APIs de IA (gratuitas)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Modelo Groq (gratuito: 14.400 req/dia)
GROQ_MODEL = "llama-3.3-70b-versatile"

# Modelo Gemini (gratuito: 1.500 req/dia)
GEMINI_MODEL = "gemini-1.5-flash"

# Configurações de busca
TOP_K_CANDIDATES = 20  # Candidatos para a IA analisar (aumentado)
SIMILARITY_THRESHOLD = 0.2  # Mínimo de similaridade (diminuído)
