"""Teste do classificador com sistema de aprendizado"""
from src.classification.classifier import ClassificadorNCM
from src.data.learning import estatisticas_historico, carregar_historico

classificador = ClassificadorNCM()
classificador.inicializar()

print()
print("="*70)
print("TESTE DO CLASSIFICADOR NCM COM APRENDIZADO")
print("="*70)

# Primeiro: classificar produtos (vai usar IA e salvar no histórico)
produtos_teste = [
    "Picanha bovina",
    "Alcatra bovina congelada",
    "Frango inteiro congelado",
]

print("\n📦 FASE 1: Classificação inicial (usa IA)")
print("-"*50)

for produto in produtos_teste:
    resultado = classificador.classificar(produto)
    print(f"\n{produto}")
    print(f"   NCM: {resultado['ncm_codigo']}")
    print(f"   Método: {resultado['metodo']}")

# Segundo: classificar os mesmos produtos (deve usar histórico)
print("\n\n📦 FASE 2: Mesmos produtos (deve usar histórico)")
print("-"*50)

for produto in produtos_teste:
    resultado = classificador.classificar(produto)
    print(f"\n{produto}")
    print(f"   NCM: {resultado['ncm_codigo']}")
    print(f"   Método: {resultado['metodo']}")  # Deve ser "historico_aprendido"

# Estatísticas
print("\n\n📊 ESTATÍSTICAS DO APRENDIZADO")
print("-"*50)
stats = estatisticas_historico()
print(f"Total classificações: {stats['total']}")
print(f"Alta confiança: {stats.get('alta_confianca', 0)}")
print(f"Prontos para treino: {stats.get('prontos_treinamento', 0)}")
