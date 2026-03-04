"""
🦈 SharkIA - Script de Setup
Prepara toda a base de dados para o classificador
"""
import sys
from pathlib import Path

# Adiciona raiz ao path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

def main():
    print("="*60)
    print("🦈 SHARKIA - SETUP INICIAL")
    print("="*60)
    
    # 1. Processar JSON oficial
    print("\n📋 ETAPA 1: Processar JSON oficial do Siscomex")
    print("-"*60)
    from src.data.parser import processar_ncm_completo, salvar_ncm_processado
    resultado = processar_ncm_completo()
    salvar_ncm_processado(resultado)
    
    # 2. Gerar embeddings
    print("\n📋 ETAPA 2: Gerar embeddings")
    print("-"*60)
    from src.search.embeddings import processar_embeddings_completo
    processar_embeddings_completo()
    
    # 3. Teste rápido
    print("\n📋 ETAPA 3: Teste de busca semântica")
    print("-"*60)
    from src.search.semantic_search import BuscaSemantica
    busca = BuscaSemantica()
    busca.carregar()
    
    queries_teste = [
        "Monitor LED",
        "Carne bovina",
        "Smartphone celular"
    ]
    
    for query in queries_teste:
        resultados = busca.buscar(query, top_k=3)
        print(f"\n🔍 '{query}':")
        for r in resultados:
            print(f"   {r['codigo']}: {r['descricao'][:40]}... ({r['score_percentual']})")
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETO!")
    print("="*60)
    print("\n📌 Próximos passos:")
    print("   1. Configure as API keys no arquivo .env")
    print("   2. Execute: python -m src.api.main")
    print("   3. Acesse: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
