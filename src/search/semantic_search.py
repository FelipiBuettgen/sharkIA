"""
Busca Semântica usando FAISS
"""
import numpy as np
import faiss
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import (
    EMBEDDINGS_PATH,
    TOP_K_CANDIDATES,
    SIMILARITY_THRESHOLD
)
from src.search.embeddings import EmbeddingGenerator


class BuscaSemantica:
    """Sistema de busca semântica para NCMs"""
    
    def __init__(self):
        self.ncms: List[Dict] = []
        self.index: Optional[faiss.Index] = None
        self.embedding_generator: Optional[EmbeddingGenerator] = None
        
    def carregar(self):
        """Carrega NCMs do banco de dados, embeddings e cria índice FAISS"""
        
        # 1. Carregar NCMs do banco de dados
        print(f"📂 Carregando NCMs do banco de dados...")
        self.ncms = self._carregar_ncms_banco()
        print(f"   ✅ {len(self.ncms)} NCMs carregados")
        
        # 2. Carregar embeddings
        print(f"📂 Carregando embeddings...")
        embeddings = np.load(EMBEDDINGS_PATH)
        print(f"   ✅ Shape: {embeddings.shape}")
        
        # 3. Criar índice FAISS
        print("🔧 Criando índice FAISS...")
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner Product (cosine após normalização)
        self.index.add(embeddings.astype('float32'))
        print(f"   ✅ Índice criado com {self.index.ntotal} vetores")
        
        # 4. Carregar modelo de embeddings
        print("🔧 Carregando modelo de embeddings...")
        self.embedding_generator = EmbeddingGenerator()
        
        print("\n✅ Sistema de busca pronto!")
    
    def _carregar_ncms_banco(self) -> List[Dict]:
        """Carrega NCMs do banco de dados SQLite"""
        from src.data.database import get_connection
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT codigo, codigo_formatado, descricao, capitulo, posicao, data_inicio, data_fim
                FROM ncms 
                WHERE ativo = 1
                ORDER BY codigo
            """)
            
            ncms = []
            for row in cursor.fetchall():
                ncms.append({
                    'codigo': row['codigo_formatado'] or row['codigo'],
                    'codigo_limpo': row['codigo'],
                    'descricao': row['descricao'],
                    'capitulo': row['capitulo'],
                    'posicao': row['posicao'],
                    'data_inicio': row['data_inicio'],
                    'data_fim': row['data_fim']
                })
            
            return ncms
        
        # 2. Carregar embeddings
        print(f"📂 Carregando embeddings...")
        embeddings = np.load(EMBEDDINGS_PATH)
        print(f"   ✅ Shape: {embeddings.shape}")
        
        # 3. Criar índice FAISS
        print("🔧 Criando índice FAISS...")
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner Product (cosine após normalização)
        self.index.add(embeddings.astype('float32'))
        print(f"   ✅ Índice criado com {self.index.ntotal} vetores")
        
        # 4. Carregar modelo de embeddings
        print("🔧 Carregando modelo de embeddings...")
        self.embedding_generator = EmbeddingGenerator()
        
        print("\n✅ Sistema de busca pronto!")
    
    def buscar(self, query: str, top_k: int = TOP_K_CANDIDATES) -> List[Dict]:
        """
        Busca NCMs mais similares à query
        
        Args:
            query: Texto de busca (ex: "Monitor LED 24 polegadas")
            top_k: Número de resultados
            
        Returns:
            Lista de NCMs com score de similaridade
        """
        if self.index is None:
            raise RuntimeError("Execute carregar() primeiro!")
        
        # Gerar embedding da query
        query_embedding = self.embedding_generator.gerar_embedding_query(query)
        
        # Buscar no FAISS
        scores, indices = self.index.search(
            query_embedding.astype('float32'), 
            top_k
        )
        
        # Montar resultados
        resultados = []
        for score, idx in zip(scores[0], indices[0]):
            if score >= SIMILARITY_THRESHOLD:
                ncm = self.ncms[idx].copy()
                ncm['score'] = float(score)
                ncm['score_percentual'] = f"{score * 100:.1f}%"
                resultados.append(ncm)
        
        return resultados
    
    def buscar_formatado(self, query: str, top_k: int = TOP_K_CANDIDATES) -> str:
        """Busca e retorna resultado formatado para exibição"""
        resultados = self.buscar(query, top_k)
        
        if not resultados:
            return f"❌ Nenhum NCM encontrado para: '{query}'"
        
        linhas = [f"🔍 Busca: '{query}'", ""]
        linhas.append(f"📋 Top {len(resultados)} resultados:\n")
        
        for i, r in enumerate(resultados, 1):
            linhas.append(f"{i}. [{r['score_percentual']}] {r['codigo']}")
            linhas.append(f"   {r['descricao']}")
            if 'palavras_chave' in r:
                linhas.append(f"   🏷️ {', '.join(r['palavras_chave'][:5])}")
            linhas.append("")
        
        return "\n".join(linhas)


def criar_indice_faiss():
    """Cria e salva índice FAISS a partir dos embeddings"""
    print("📂 Carregando embeddings...")
    embeddings = np.load(EMBEDDINGS_PATH)
    
    print(f"🔧 Criando índice FAISS (dimension={embeddings.shape[1]})...")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings.astype('float32'))
    
    print(f"💾 Salvando índice em: {FAISS_INDEX_PATH}")
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    
    print(f"✅ Índice criado com {index.ntotal} vetores")


# Instância global para reutilização
_busca_global: Optional[BuscaSemantica] = None

def get_busca() -> BuscaSemantica:
    """Retorna instância global do sistema de busca"""
    global _busca_global
    if _busca_global is None:
        _busca_global = BuscaSemantica()
        _busca_global.carregar()
    return _busca_global


if __name__ == "__main__":
    # Teste interativo
    busca = BuscaSemantica()
    busca.carregar()
    
    print("\n" + "="*60)
    print("🔍 TESTE DE BUSCA SEMÂNTICA")
    print("="*60)
    
    queries_teste = [
        "Monitor LED 24 polegadas",
        "Notebook Dell Inspiron",
        "Carne bovina congelada",
        "Parafuso de aço inoxidável",
        "Celular iPhone smartphone"
    ]
    
    for query in queries_teste:
        print(busca.buscar_formatado(query, top_k=3))
        print("-"*60)
