"""Teste de busca"""
from src.search.semantic_search import BuscaSemantica

busca = BuscaSemantica()
busca.carregar()

testes = [
    "Picanha bovina",
    "Carne bovina congelada",
    "Monitor LED 24 polegadas",
    "Smartphone Samsung",
    "Notebook Dell"
]

for query in testes:
    print(f"\n🔍 {query}")
    print("-" * 50)
    resultados = busca.buscar(query, top_k=5)
    for r in resultados:
        codigo = r['codigo']
        desc = r['descricao'][:45]
        score = r['score_percentual']
        print(f"  {codigo}: {desc}... ({score})")
