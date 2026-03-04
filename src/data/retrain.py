"""
Re-treina embeddings usando dados aprendidos do histórico
Adiciona os produtos classificados pela IA como sinônimos dos NCMs
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import (
    NCM_PROCESSADO_PATH, 
    NCM_ENRIQUECIDO_PATH,
    EMBEDDINGS_PATH,
    DATA_DIR
)
from src.data.learning import carregar_historico, gerar_dados_treinamento


def enriquecer_ncms_com_historico() -> Dict:
    """
    Enriquece NCMs com dados aprendidos do histórico
    Cada produto classificado vira um "sinônimo" do NCM
    """
    print("📂 Carregando NCMs processados...")
    with open(NCM_PROCESSADO_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ncms = data['ncms']
    print(f"   Total NCMs: {len(ncms)}")
    
    # Gerar dados de treinamento do histórico
    print("\n📚 Gerando dados de treinamento do histórico...")
    dados_treino = gerar_dados_treinamento()
    print(f"   Registros de treinamento: {len(dados_treino)}")
    
    if not dados_treino:
        print("⚠️ Nenhum dado de treinamento disponível ainda.")
        print("   Execute classificações com IA para acumular dados.")
        return data
    
    # Agrupar produtos por NCM
    produtos_por_ncm = defaultdict(list)
    for item in dados_treino:
        produtos_por_ncm[item['ncm_codigo']].append(item['produto'])
    
    print(f"   NCMs com dados de aprendizado: {len(produtos_por_ncm)}")
    
    # Enriquecer NCMs
    enriquecidos = 0
    for ncm in ncms:
        codigo = ncm['codigo']
        if codigo in produtos_por_ncm:
            # Adiciona produtos aprendidos como termos de busca
            termos_aprendidos = produtos_por_ncm[codigo]
            
            if 'termos_aprendidos' not in ncm:
                ncm['termos_aprendidos'] = []
            
            # Adiciona apenas termos novos
            for termo in termos_aprendidos:
                if termo not in ncm['termos_aprendidos']:
                    ncm['termos_aprendidos'].append(termo)
            
            enriquecidos += 1
    
    print(f"   NCMs enriquecidos: {enriquecidos}")
    
    # Atualizar metadata
    data['metadata']['enriquecido_com_historico'] = True
    data['metadata']['total_termos_aprendidos'] = len(dados_treino)
    
    return data


def salvar_ncms_enriquecidos(data: Dict):
    """Salva NCMs enriquecidos"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(NCM_ENRIQUECIDO_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Salvo em: {NCM_ENRIQUECIDO_PATH}")


def regenerar_embeddings():
    """Regenera embeddings com dados enriquecidos"""
    from src.search.embeddings import EmbeddingGenerator
    
    print("\n🔧 Carregando NCMs enriquecidos...")
    with open(NCM_ENRIQUECIDO_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ncms = data['ncms']
    
    # Preparar textos incluindo termos aprendidos
    print("📝 Preparando textos para embeddings...")
    textos = []
    for ncm in ncms:
        texto = f"{ncm['codigo']} {ncm['descricao']}"
        
        # Adicionar termos aprendidos
        if 'termos_aprendidos' in ncm and ncm['termos_aprendidos']:
            texto += " " + " ".join(ncm['termos_aprendidos'])
        
        # Adicionar palavras-chave se existirem
        if 'palavras_chave' in ncm and ncm['palavras_chave']:
            texto += " " + " ".join(ncm['palavras_chave'])
        
        textos.append(texto)
    
    # Gerar embeddings
    print("🧮 Gerando embeddings...")
    generator = EmbeddingGenerator()
    embeddings = generator.model.encode(
        textos,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    
    # Salvar
    np.save(EMBEDDINGS_PATH, embeddings)
    print(f"💾 Embeddings salvos: {embeddings.shape}")


def retreinar_completo():
    """Pipeline completo de re-treinamento"""
    print("="*60)
    print("🔄 RE-TREINAMENTO COM DADOS APRENDIDOS")
    print("="*60)
    
    # 1. Enriquecer NCMs com histórico
    data = enriquecer_ncms_com_historico()
    salvar_ncms_enriquecidos(data)
    
    # 2. Regenerar embeddings
    regenerar_embeddings()
    
    print("\n" + "="*60)
    print("✅ RE-TREINAMENTO CONCLUÍDO!")
    print("="*60)
    print("\nO modelo agora inclui os termos aprendidos.")
    print("Reinicie a API para usar o modelo atualizado.")


if __name__ == "__main__":
    retreinar_completo()
