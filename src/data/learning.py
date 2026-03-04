"""
Sistema de Aprendizado - Salva classificações para treinar modelo local
Agora usa SQLite para melhor escalabilidade e concorrência
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import DATA_DIR

# Importar módulo de banco de dados
from src.data.database import (
    inserir_classificacao,
    buscar_classificacoes,
    buscar_classificacao_exata,
    validar_classificacao as db_validar_classificacao,
    obter_todas_classificacoes,
    estatisticas_banco,
    migrar_de_json
)


# Arquivo de histórico legado (para migração)
HISTORICO_PATH = DATA_DIR / "historico_classificacoes.json"
DADOS_TREINAMENTO_PATH = DATA_DIR / "dados_treinamento.json"


def carregar_historico() -> List[Dict]:
    """
    Carrega histórico de classificações do SQLite
    Mantém compatibilidade com código existente
    """
    return obter_todas_classificacoes()


def salvar_historico(historico: List[Dict]):
    """
    Função legada - não mais necessária com SQLite
    Mantida para compatibilidade, mas não faz nada
    """
    # SQLite salva automaticamente em cada inserção
    pass


def registrar_classificacao(
    produto: str,
    ncm_codigo: str,
    ncm_descricao: str,
    confianca: str,
    metodo: str,
    justificativa: str = "",
    validado_usuario: bool = False,
    score_match: float = 0.0
) -> Dict:
    """
    Registra uma classificação no SQLite para aprendizado
    
    Args:
        produto: Descrição do produto
        ncm_codigo: NCM classificado
        ncm_descricao: Descrição do NCM
        confianca: alta/media/baixa
        metodo: busca_semantica/ia_groq/ia_gemini
        justificativa: Explicação da IA
        validado_usuario: Se o usuário confirmou que está correto
        score_match: Score de similaridade semântica (0 a 1)
    
    Returns:
        Registro criado
    """
    return inserir_classificacao(
        produto=produto,
        ncm_codigo=ncm_codigo,
        ncm_descricao=ncm_descricao,
        confianca=confianca,
        metodo=metodo,
        justificativa=justificativa,
        validado_usuario=validado_usuario,
        score_match=score_match
    )


def validar_classificacao(registro_id: str, correto: bool, ncm_correto: str = None):
    """
    Usuário valida se classificação está correta
    
    Args:
        registro_id: ID do registro
        correto: Se a classificação estava correta
        ncm_correto: NCM correto (se o original estava errado)
    """
    db_validar_classificacao(registro_id, correto, ncm_correto)


def gerar_dados_treinamento() -> List[Dict]:
    """
    Gera dados de treinamento a partir do histórico SQLite
    Usa apenas classificações validadas ou de alta confiança
    """
    historico = obter_todas_classificacoes()
    dados = []
    
    for reg in historico:
        # Usa se: validado pelo usuário OU confiança alta da IA
        usar = False
        ncm = reg['ncm_codigo']
        
        if reg.get('validado_usuario'):
            if reg.get('classificacao_correta', True):
                usar = True
            elif reg.get('ncm_corrigido'):
                # Usuário corrigiu, usa o NCM correto
                ncm = reg['ncm_corrigido']
                usar = True
        elif reg.get('confianca') == 'alta' and str(reg.get('metodo', '')).startswith('ia_'):
            # Alta confiança da IA
            usar = True
        
        if usar:
            dados.append({
                "produto": reg['produto'],
                "ncm_codigo": ncm,
                "ncm_descricao": reg.get('ncm_descricao', ''),
                "fonte": "historico"
            })
    
    # Salvar dados de treinamento
    with open(DADOS_TREINAMENTO_PATH, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    
    return dados


def estatisticas_historico() -> Dict:
    """Retorna estatísticas do histórico usando SQLite"""
    stats = estatisticas_banco()
    
    if stats['total'] == 0:
        return {"total": 0}
    
    return {
        "total": stats['total'],
        "validados_usuario": stats['validados'],
        "alta_confianca": stats['alta_confianca'],
        "prontos_treinamento": stats['validados'] + stats['alta_confianca'],
        "por_metodo": stats['por_metodo'],
        "top_ncms": stats.get('top_ncms', [])
    }


def buscar_no_historico(produto: str) -> Optional[Dict]:
    """
    Busca produto no histórico para cache/aprendizado
    Retorna classificação se encontrar com alta confiança
    """
    return buscar_classificacao_exata(produto)


def migrar_json_para_sqlite():
    """
    Migra dados do histórico JSON antigo para SQLite
    Execute uma vez para migrar dados existentes
    """
    if HISTORICO_PATH.exists():
        count = migrar_de_json(HISTORICO_PATH)
        if count > 0:
            # Renomear arquivo antigo como backup
            backup_path = HISTORICO_PATH.with_suffix('.json.bak')
            HISTORICO_PATH.rename(backup_path)
            print(f"📦 Backup do JSON antigo: {backup_path}")
        return count
    return 0


if __name__ == "__main__":
    # Migrar dados antigos se existirem
    if HISTORICO_PATH.exists():
        print("🔄 Migrando dados do JSON para SQLite...")
        migrar_json_para_sqlite()
    
    # Exibir estatísticas
    print("\n📊 Estatísticas do histórico:")
    stats = estatisticas_historico()
    print(f"   Total: {stats['total']}")
    print(f"   Validados: {stats.get('validados_usuario', 0)}")
    print(f"   Alta confiança: {stats.get('alta_confianca', 0)}")
    print(f"   Prontos para treino: {stats.get('prontos_treinamento', 0)}")
    if stats.get('por_metodo'):
        print(f"   Por método: {stats['por_metodo']}")
