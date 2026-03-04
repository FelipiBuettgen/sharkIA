"""
Enriquecedor de NCMs
Adiciona palavras-chave e sinônimos para melhorar a busca semântica
"""
import json
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import NCM_PROCESSADO_PATH, NCM_ENRIQUECIDO_PATH, DATA_DIR


# Dicionário de enriquecimento manual para categorias importantes
# Chave pode ser: posição (4 dígitos sem ponto) ou NCM completo (8 dígitos com pontos)
ENRIQUECIMENTO_MANUAL = {
    # ========== CARNES BOVINAS ==========
    # Carnes bovinas frescas/refrigeradas
    "0201.30.00": {
        "palavras_chave": ["carne", "bovina", "boi", "vaca", "fresca", "refrigerada", "desossada", "corte", "açougue"],
        "exemplos": ["picanha", "alcatra", "filé mignon", "contrafilé", "maminha", "fraldinha", "patinho", "coxão mole", "coxão duro", "lagarto", "músculo", "acém", "cupim"]
    },
    "0201.20.20": {
        "palavras_chave": ["carne", "bovina", "boi", "quarto", "traseiro", "fresca", "refrigerada"],
        "exemplos": ["picanha", "alcatra", "maminha", "coxão", "lagarto", "patinho"]
    },
    "0201.20.10": {
        "palavras_chave": ["carne", "bovina", "boi", "quarto", "dianteiro", "fresca", "refrigerada"],
        "exemplos": ["acém", "peito", "paleta", "músculo dianteiro"]
    },
    # Carnes bovinas congeladas
    "0202.30.00": {
        "palavras_chave": ["carne", "bovina", "boi", "vaca", "congelada", "desossada", "corte", "açougue"],
        "exemplos": ["picanha congelada", "alcatra congelada", "filé mignon congelado", "contrafilé congelado", "maminha congelada", "fraldinha congelada"]
    },
    "0202.20.20": {
        "palavras_chave": ["carne", "bovina", "boi", "quarto", "traseiro", "congelada"],
        "exemplos": ["picanha congelada", "alcatra congelada", "maminha congelada"]
    },
    # Costela bovina
    "0201.10.00": {
        "palavras_chave": ["carcaça", "meia-carcaça", "boi", "bovina", "inteira"],
        "exemplos": ["boi inteiro", "meia carcaça", "carcaça bovina"]
    },
    # Posições genéricas (4 dígitos)
    "0201": {
        "palavras_chave": ["carne", "bovina", "boi", "vaca", "fresca", "refrigerada", "corte", "açougue", "churrasco"],
        "exemplos": ["picanha", "alcatra", "filé mignon", "contrafilé", "maminha", "fraldinha", "costela", "acém", "patinho", "coxão mole", "coxão duro", "lagarto", "músculo", "cupim", "t-bone"]
    },
    "0202": {
        "palavras_chave": ["carne", "bovina", "boi", "vaca", "congelada", "corte", "açougue", "churrasco"],
        "exemplos": ["picanha congelada", "alcatra congelada", "filé mignon congelado", "contrafilé congelado", "costela congelada", "maminha congelada"]
    },
    # Frango
    "0207": {
        "palavras_chave": ["frango", "galinha", "ave", "aves", "peru", "pato"],
        "exemplos": ["peito de frango", "coxa", "sobrecoxa", "asa", "frango inteiro", "filé de frango"]
    },
    # Peixes
    "0302": {
        "palavras_chave": ["peixe", "fresco", "refrigerado", "pescado"],
        "exemplos": ["salmão", "tilápia", "bacalhau", "sardinha", "atum", "robalo", "dourado"]
    },
    "0303": {
        "palavras_chave": ["peixe", "congelado", "pescado"],
        "exemplos": ["salmão congelado", "tilápia congelada", "filé de peixe congelado"]
    },
    # Eletrônicos
    "8471": {
        "palavras_chave": ["computador", "notebook", "laptop", "pc", "desktop", "processamento", "dados"],
        "exemplos": ["notebook Dell", "notebook Lenovo", "MacBook", "computador desktop", "PC gamer"]
    },
    "8517": {
        "palavras_chave": ["telefone", "celular", "smartphone", "comunicação", "móvel"],
        "exemplos": ["iPhone", "Samsung Galaxy", "Motorola", "Xiaomi", "smartphone Android"]
    },
    "8528": {
        "palavras_chave": ["monitor", "tela", "display", "vídeo", "televisor", "tv"],
        "exemplos": ["monitor Dell", "monitor LG", "monitor Samsung", "TV LED", "televisão"]
    },
    # Máquinas
    "8418": {
        "palavras_chave": ["refrigerador", "geladeira", "freezer", "congelador", "refrigeração"],
        "exemplos": ["geladeira Brastemp", "freezer vertical", "refrigerador duplex"]
    },
    "8450": {
        "palavras_chave": ["máquina", "lavar", "roupa", "lavadora", "lava-roupa"],
        "exemplos": ["máquina de lavar Brastemp", "lavadora Electrolux", "lava e seca"]
    },
    # Veículos
    "8703": {
        "palavras_chave": ["automóvel", "carro", "veículo", "transporte", "passageiros"],
        "exemplos": ["carro sedan", "SUV", "hatch", "Corolla", "Civic", "Onix"]
    },
    "8711": {
        "palavras_chave": ["motocicleta", "moto", "motociclo", "duas rodas"],
        "exemplos": ["moto Honda", "Yamaha", "CG 160", "Biz", "PCX"]
    },
    # Alimentos processados
    "1601": {
        "palavras_chave": ["embutido", "salsicha", "linguiça", "carne processada"],
        "exemplos": ["salsicha", "linguiça calabresa", "linguiça toscana", "mortadela"]
    },
    "1602": {
        "palavras_chave": ["carne", "preparada", "conserva", "enlatada"],
        "exemplos": ["carne enlatada", "corned beef", "carne seca", "charque"]
    },
    # Bebidas
    "2203": {
        "palavras_chave": ["cerveja", "malte", "bebida", "alcoólica"],
        "exemplos": ["cerveja pilsen", "cerveja IPA", "cerveja artesanal", "Brahma", "Skol"]
    },
    "2204": {
        "palavras_chave": ["vinho", "uva", "bebida", "alcoólica"],
        "exemplos": ["vinho tinto", "vinho branco", "vinho rosé", "espumante", "champagne"]
    },
    # Vestuário
    "6109": {
        "palavras_chave": ["camiseta", "t-shirt", "malha", "roupa", "vestuário"],
        "exemplos": ["camiseta algodão", "t-shirt", "regata", "blusa"]
    },
    "6203": {
        "palavras_chave": ["calça", "bermuda", "shorts", "roupa", "masculina"],
        "exemplos": ["calça jeans", "bermuda", "shorts", "calça social"]
    },
}


def enriquecer_ncm(ncm: Dict) -> Dict:
    """
    Enriquece um NCM com palavras-chave e exemplos
    """
    import re
    ncm_enriquecido = ncm.copy()
    codigo = ncm['codigo']  # Ex: "0201.30.00"
    
    # Extrair posição (4 dígitos) - Ex: "0201"
    posicao = codigo.replace('.', '')[:4]
    
    palavras_chave = []
    exemplos = []
    
    # 1. Verificar se há enriquecimento para o NCM completo
    if codigo in ENRIQUECIMENTO_MANUAL:
        enriq = ENRIQUECIMENTO_MANUAL[codigo]
        palavras_chave.extend(enriq.get('palavras_chave', []))
        exemplos.extend(enriq.get('exemplos', []))
    
    # 2. Verificar se há enriquecimento para a posição (4 dígitos)
    if posicao in ENRIQUECIMENTO_MANUAL:
        enriq = ENRIQUECIMENTO_MANUAL[posicao]
        palavras_chave.extend(enriq.get('palavras_chave', []))
        exemplos.extend(enriq.get('exemplos', []))
    
    # 3. Extrair palavras da descrição como palavras-chave adicionais
    descricao = ncm['descricao'].lower()
    # Remover tags HTML
    descricao = re.sub(r'<[^>]+>', '', descricao)
    
    # Adicionar palavras da descrição (maiores que 3 caracteres)
    palavras_desc = [p for p in re.findall(r'\b\w+\b', descricao) if len(p) > 3]
    palavras_chave.extend(palavras_desc)
    
    # Remover duplicatas mantendo ordem
    palavras_chave = list(dict.fromkeys(palavras_chave))
    exemplos = list(dict.fromkeys(exemplos))
    
    ncm_enriquecido['palavras_chave'] = palavras_chave
    ncm_enriquecido['exemplos_produtos'] = exemplos
    
    return ncm_enriquecido


def processar_enriquecimento():
    """
    Processa todos os NCMs e adiciona enriquecimento
    """
    print("📂 Carregando NCMs processados...")
    with open(NCM_PROCESSADO_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ncms = data['ncms']
    print(f"   Total: {len(ncms)} NCMs")
    
    print("\n🔧 Enriquecendo NCMs...")
    ncms_enriquecidos = []
    for ncm in tqdm(ncms, desc="Enriquecendo"):
        ncm_enriquecido = enriquecer_ncm(ncm)
        ncms_enriquecidos.append(ncm_enriquecido)
    
    # Atualizar dados
    data['ncms'] = ncms_enriquecidos
    
    # Salvar
    print(f"\n💾 Salvando em: {NCM_ENRIQUECIDO_PATH}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(NCM_ENRIQUECIDO_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Mostrar exemplos
    print("\n📋 Exemplos de NCMs enriquecidos:")
    for ncm in ncms_enriquecidos[:5]:
        print(f"\n   {ncm['codigo']}: {ncm['descricao'][:40]}...")
        if ncm['palavras_chave']:
            print(f"   🏷️ Palavras: {', '.join(ncm['palavras_chave'][:5])}")
        if ncm['exemplos_produtos']:
            print(f"   📦 Exemplos: {', '.join(ncm['exemplos_produtos'][:3])}")
    
    print("\n✅ Enriquecimento concluído!")
    return data


if __name__ == "__main__":
    processar_enriquecimento()
