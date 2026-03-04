"""
Gerador de Embeddings usando Sentence Transformers
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from tqdm import tqdm

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import (
    EMBEDDING_MODEL, 
    EMBEDDING_DIMENSION,
    NCM_PROCESSADO_PATH,
    NCM_ENRIQUECIDO_PATH,
    EMBEDDINGS_PATH,
    DATA_DIR
)


class EmbeddingGenerator:
    """Gera embeddings para NCMs usando modelos locais gratuitos"""
    
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        print(f"🔄 Carregando modelo: {model_name}...")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        print("✅ Modelo carregado!")
    
    def criar_texto_ncm(self, ncm: Dict) -> str:
        """
        Cria texto rico para embedding.
        Se tiver enriquecimento, usa. Senão, usa descrição básica.
        """
        codigo = ncm['codigo']
        descricao = ncm['descricao']
        
        # Texto básico
        texto = f"{codigo} {descricao}"
        
        # Se tiver dados enriquecidos, adiciona
        if 'palavras_chave' in ncm:
            texto += " " + " ".join(ncm['palavras_chave'])
        
        if 'exemplos_produtos' in ncm:
            texto += " " + " ".join(ncm['exemplos_produtos'])
        
        if 'categoria_comercial' in ncm:
            texto += " " + ncm['categoria_comercial']
        
        return texto
    
    def gerar_embeddings(self, ncms: List[Dict], batch_size: int = 64) -> np.ndarray:
        """
        Gera embeddings para lista de NCMs
        """
        print(f"\n📝 Criando textos para {len(ncms)} NCMs...")
        textos = [self.criar_texto_ncm(ncm) for ncm in ncms]
        
        print(f"🧮 Gerando embeddings (batch_size={batch_size})...")
        embeddings = self.model.encode(
            textos,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True  # Normaliza para cosine similarity
        )
        
        print(f"✅ Embeddings gerados: shape {embeddings.shape}")
        return embeddings
    
    def gerar_embedding_query(self, texto: str) -> np.ndarray:
        """Gera embedding para uma query de busca"""
        embedding = self.model.encode(
            [texto],
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embedding
    
    def salvar_embeddings(self, embeddings: np.ndarray, caminho: Path = EMBEDDINGS_PATH):
        """Salva embeddings em arquivo numpy"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        np.save(caminho, embeddings)
        print(f"💾 Embeddings salvos em: {caminho}")
    
    def carregar_embeddings(self, caminho: Path = EMBEDDINGS_PATH) -> np.ndarray:
        """Carrega embeddings de arquivo"""
        return np.load(caminho)


def processar_embeddings_completo():
    """Pipeline completo: carrega NCMs e gera embeddings"""
    
    # Tenta carregar versão enriquecida, senão usa básica
    if NCM_ENRIQUECIDO_PATH.exists():
        print("📂 Usando NCMs enriquecidos...")
        with open(NCM_ENRIQUECIDO_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    elif NCM_PROCESSADO_PATH.exists():
        print("📂 Usando NCMs processados (sem enriquecimento)...")
        with open(NCM_PROCESSADO_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        raise FileNotFoundError(
            "Execute primeiro: python src/data/parser.py"
        )
    
    ncms = data['ncms']
    print(f"📊 Total de NCMs: {len(ncms)}")
    
    # Gerar embeddings
    generator = EmbeddingGenerator()
    embeddings = generator.gerar_embeddings(ncms)
    generator.salvar_embeddings(embeddings)
    
    return embeddings


if __name__ == "__main__":
    processar_embeddings_completo()
