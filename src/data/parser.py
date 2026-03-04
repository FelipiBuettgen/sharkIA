"""
Parser do JSON oficial do Siscomex
Extrai apenas NCMs de 8 dígitos (classificáveis)
"""
import json
import re
from pathlib import Path
from typing import List, Dict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import NCM_JSON_PATH, NCM_PROCESSADO_PATH, DATA_DIR


def carregar_json_oficial(caminho: Path = NCM_JSON_PATH) -> Dict:
    """Carrega o JSON oficial do Siscomex"""
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)


def filtrar_ncm_8_digitos(data: Dict) -> List[Dict]:
    """
    Filtra apenas NCMs de 8 dígitos (formato: XXXX.XX.XX)
    Esses são os códigos classificáveis para produtos
    """
    ncms_8_digitos = []
    
    for ncm in data['Nomenclaturas']:
        codigo = ncm['Codigo']
        # Verifica se é formato XXXX.XX.XX (8 dígitos)
        if re.match(r'^\d{4}\.\d{2}\.\d{2}$', codigo):
            ncms_8_digitos.append({
                'codigo': codigo,
                'codigo_limpo': codigo.replace('.', ''),
                'descricao': ncm['Descricao'].strip('- '),
                'capitulo': codigo[:2],
                'posicao': codigo[:7],  # XXXX.XX
                'data_inicio': ncm.get('Data_Inicio', ''),
                'data_fim': ncm.get('Data_Fim', ''),
            })
    
    return ncms_8_digitos


def criar_hierarquia_ncm(data: Dict) -> Dict[str, Dict]:
    """
    Cria mapeamento hierárquico:
    Capítulo (2 dig) → Posição (4 dig) → Subposição (6 dig) → NCM (8 dig)
    """
    hierarquia = {
        'capitulos': {},
        'posicoes': {},
        'subposicoes': {}
    }
    
    for ncm in data['Nomenclaturas']:
        codigo = ncm['Codigo']
        codigo_limpo = codigo.replace('.', '')
        descricao = ncm['Descricao'].strip('- ')
        
        # Capítulo (2 dígitos): 01, 02, 03...
        if re.match(r'^\d{2}$', codigo_limpo):
            hierarquia['capitulos'][codigo] = descricao
            
        # Posição (4 dígitos): 01.01, 01.02...
        elif re.match(r'^\d{4}$', codigo_limpo):
            hierarquia['posicoes'][codigo] = descricao
            
        # Subposição (6 dígitos): 0101.21, 0101.29...
        elif re.match(r'^\d{6}$', codigo_limpo):
            hierarquia['subposicoes'][codigo] = descricao
    
    return hierarquia


def processar_ncm_completo() -> Dict:
    """
    Processa o JSON oficial e retorna estrutura completa
    """
    print("📂 Carregando JSON oficial...")
    data = carregar_json_oficial()
    
    print(f"📅 Data de atualização: {data['Data_Ultima_Atualizacao_NCM']}")
    print(f"📜 Ato legal: {data['Ato']}")
    print(f"📊 Total de registros: {len(data['Nomenclaturas'])}")
    
    print("\n🔍 Filtrando NCMs de 8 dígitos...")
    ncms = filtrar_ncm_8_digitos(data)
    print(f"✅ NCMs classificáveis encontrados: {len(ncms)}")
    
    print("\n🏗️ Criando hierarquia...")
    hierarquia = criar_hierarquia_ncm(data)
    print(f"   Capítulos: {len(hierarquia['capitulos'])}")
    print(f"   Posições: {len(hierarquia['posicoes'])}")
    print(f"   Subposições: {len(hierarquia['subposicoes'])}")
    
    resultado = {
        'metadata': {
            'data_atualizacao': data['Data_Ultima_Atualizacao_NCM'],
            'ato_legal': data['Ato'],
            'total_ncms': len(ncms)
        },
        'hierarquia': hierarquia,
        'ncms': ncms
    }
    
    return resultado


def salvar_ncm_processado(resultado: Dict, caminho: Path = NCM_PROCESSADO_PATH):
    """Salva o resultado processado em JSON"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Salvo em: {caminho}")


def carregar_ncm_processado(caminho: Path = NCM_PROCESSADO_PATH) -> Dict:
    """Carrega NCMs processados"""
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == "__main__":
    resultado = processar_ncm_completo()
    salvar_ncm_processado(resultado)
    
    # Mostrar exemplos
    print("\n📋 Exemplos de NCMs processados:")
    for ncm in resultado['ncms'][:5]:
        print(f"   {ncm['codigo']}: {ncm['descricao'][:50]}...")
