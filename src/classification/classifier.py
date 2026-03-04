"""
Classificador NCM - Integra busca semântica + IA
"""
from typing import Dict, Optional, List
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import TOP_K_CANDIDATES, GROQ_API_KEY, GEMINI_API_KEY


class ClassificadorNCM:

    def __init__(self, provider: str = "auto", busca_externa=None):

        self.busca = busca_externa
        self.ia_client = None
        self.provider = provider
        
    def inicializar(self):
        print("Inicializando ClassificadorNCM...")
        
        # 1. Carregar busca semântica (se não foi passada externa)
        if self.busca is None:
            from src.search.semantic_search import BuscaSemantica
            self.busca = BuscaSemantica()
            self.busca.carregar()
        else:
            print("♻️ Reutilizando instância de BuscaSemântica existente")
        
        # 2. Configurar cliente de IA
        self._configurar_ia()
        
        print("\n✅ Classificador pronto para uso!")
    
    def _configurar_ia(self):
        """Configura cliente de IA baseado na disponibilidade"""
        
        if self.provider == "groq" or (self.provider == "auto" and GROQ_API_KEY):
            try:
                from src.classification.groq_client import GroqClient
                self.ia_client = GroqClient()
                self.provider = "groq"
                print("Usando Groq (Llama 3.1)")
                return
            except Exception as e:
                print(f"Groq não disponível: {e}")
        
        if self.provider == "gemini" or (self.provider == "auto" and GEMINI_API_KEY):
            try:
                from src.classification.gemini_client import GeminiClient
                self.ia_client = GeminiClient()
                self.provider = "gemini"
                print("Usando Google Gemini")
                return
            except Exception as e:
                print(f"Gemini não disponível: {e}")
        
        print("Nenhuma API de IA configurada. Usando apenas busca semântica.")
        self.ia_client = None
    
    def classificar(
        self, 
        produto: str,
        usar_ia: bool = True,
        top_k: int = TOP_K_CANDIDATES,
        salvar_historico: bool = True,
        pular_historico: bool = False
    ) -> Dict:
        """
        Classifica um produto em NCM
        
        Pipeline:
        1. Verifica se já existe no histórico (aprendizado)
        2. Se não, faz busca semântica
        3. Se usar_ia=True, usa IA para decisão final
        4. Salva resultado no histórico para aprendizado futuro
        
        Args:
            produto: Descrição do produto
            usar_ia: Se True, usa IA para decisão final
            top_k: Número de candidatos da busca semântica
            salvar_historico: Se True, salva para aprendizado
            pular_historico: Se True, não busca no histórico (útil para completar opções)
            
        Returns:
            Dict com NCM classificado e detalhes
        """
        if self.busca is None:
            raise RuntimeError("Execute inicializar() primeiro!")
        
        # 0. VERIFICAR HISTÓRICO - Busca exata ou similar (se não pular)
        if not pular_historico:
            resultado_historico = self._buscar_no_historico(produto)
            if resultado_historico:
                return resultado_historico
        
        # 1. Busca semântica
        candidatos = self.busca.buscar(produto, top_k=top_k)
        
        if not candidatos:
            return {
                "sucesso": False,
                "produto": produto,
                "erro": "Nenhum NCM encontrado na busca semântica",
                "candidatos": []
            }
        
        # 2. Se não usar IA ou não tiver cliente, retorna top 1 da busca
        if not usar_ia or self.ia_client is None:
            melhor = candidatos[0]
            resultado = {
                "sucesso": True,
                "produto": produto,
                "ncm_codigo": melhor['codigo'],
                "ncm_descricao": melhor['descricao'],
                "confianca": "media",
                "metodo": "busca_semantica",
                "score_similaridade": melhor['score'],
                "candidatos": candidatos[:5]
            }
            # Salvar no histórico (mas com confiança média)
            if salvar_historico:
                self._salvar_no_historico(resultado)
            return resultado
        
        # 3. VERIFICAR CACHE DE IA (evita chamadas repetidas)
        cache_resultado = self._buscar_cache_ia(produto)
        if cache_resultado:
            resultado = {
                "sucesso": True,
                "produto": produto,
                "ncm_codigo": cache_resultado['ncm_codigo'],
                "ncm_descricao": cache_resultado.get('ncm_descricao', ''),
                "confianca": cache_resultado.get('confianca', 'alta'),
                "justificativa": cache_resultado.get('justificativa', '') + " [cache]",
                "metodo": f"cache_{cache_resultado.get('provider', 'ia')}",
                "modelo": cache_resultado.get('modelo', ''),
                "score_similaridade": 1.0,
                "candidatos": candidatos[:5]
            }
            return resultado
        
        # 4. Usar IA para decisão final
        resultado_ia = self.ia_client.classificar_ncm(produto, candidatos)
        
        # Encontrar dados completos do NCM escolhido
        ncm_escolhido = resultado_ia.get('ncm_codigo')
        
        # Primeiro tenta encontrar nos candidatos
        ncm_dados = next(
            (c for c in candidatos if c['codigo'] == ncm_escolhido),
            None
        )
        
        # Se não encontrou nos candidatos, busca na base completa
        # (IA pode sugerir NCM correto fora dos candidatos)
        if ncm_dados is None and ncm_escolhido:
            ncm_dados = next(
                (n for n in self.busca.ncms if n['codigo'] == ncm_escolhido),
                None
            )
            if ncm_dados:
                ncm_dados = ncm_dados.copy()
                ncm_dados['score'] = 0.0
                ncm_dados['score_percentual'] = "IA"
        
        # Fallback para primeiro candidato se nada funcionou
        if ncm_dados is None:
            ncm_dados = candidatos[0]
        
        resultado = {
            "sucesso": True,
            "produto": produto,
            "ncm_codigo": ncm_dados.get('codigo', ncm_escolhido),
            "ncm_descricao": ncm_dados.get('descricao', 'NCM sugerido pela IA'),
            "confianca": resultado_ia.get('confianca', 'media'),
            "justificativa": resultado_ia.get('justificativa', ''),
            "metodo": f"ia_{resultado_ia.get('provider', 'unknown')}",
            "modelo": resultado_ia.get('modelo', ''),
            "score_similaridade": ncm_dados.get('score', 0),
            "candidatos": candidatos[:5]
        }
        
        # 5. SALVAR NO CACHE DE IA (para evitar chamadas repetidas)
        self._salvar_cache_ia(resultado)
        
        # 6. SALVAR NO HISTÓRICO para aprendizado
        if salvar_historico:
            self._salvar_no_historico(resultado)
        
        return resultado
    
    def _buscar_no_historico(self, produto: str) -> Optional[Dict]:
        """
        Busca produto no histórico de classificações aprendidas
        Retorna resultado se encontrar com alta confiança
        """
        try:
            from src.data.learning import carregar_historico
            historico = carregar_historico()
            
            # Normalizar produto para comparação
            produto_lower = produto.lower().strip()
            
            for reg in historico:
                # Busca exata (case insensitive)
                if reg['produto'].lower().strip() == produto_lower:
                    # Só usa se tiver alta confiança ou foi validado
                    if reg.get('confianca') == 'alta' or reg.get('validado_usuario'):
                        return {
                            "sucesso": True,
                            "produto": produto,
                            "ncm_codigo": reg.get('ncm_corrigido', reg['ncm_codigo']),
                            "ncm_descricao": reg['ncm_descricao'],
                            "confianca": "alta",
                            "justificativa": "Classificação recuperada do histórico (aprendizado)",
                            "metodo": "historico_aprendido",
                            "score_similaridade": 1.0,
                            "candidatos": []
                        }
        except Exception:
            pass
        
        return None
    
    def _salvar_no_historico(self, resultado: Dict):
        """Salva classificação no histórico para aprendizado"""
        try:
            from src.data.learning import registrar_classificacao
            registrar_classificacao(
                produto=resultado['produto'],
                ncm_codigo=resultado['ncm_codigo'],
                ncm_descricao=resultado.get('ncm_descricao', ''),
                confianca=resultado.get('confianca', 'media'),
                metodo=resultado.get('metodo', 'desconhecido'),
                justificativa=resultado.get('justificativa', ''),
                score_match=resultado.get('score_match', 0.0)
            )
        except Exception as e:
            print(f"⚠️ Erro ao salvar no histórico: {e}")
    
    def _buscar_cache_ia(self, produto: str) -> Optional[Dict]:
        """Busca resposta em cache para evitar chamadas repetidas à IA"""
        try:
            from src.data.database import buscar_cache_ia
            return buscar_cache_ia(produto)
        except Exception:
            return None
    
    def _salvar_cache_ia(self, resultado: Dict):
        """Salva resposta da IA em cache"""
        try:
            from src.data.database import salvar_cache_ia
            salvar_cache_ia(
                produto=resultado['produto'],
                ncm_codigo=resultado['ncm_codigo'],
                ncm_descricao=resultado.get('ncm_descricao', ''),
                confianca=resultado.get('confianca', 'media'),
                justificativa=resultado.get('justificativa', ''),
                provider=resultado.get('metodo', '').replace('ia_', ''),
                modelo=resultado.get('modelo', '')
            )
        except Exception as e:
            print(f"⚠️ Erro ao salvar cache: {e}")
    
    def classificar_lote(
        self, 
        produtos: List[str],
        usar_ia: bool = True
    ) -> List[Dict]:
        """Classifica múltiplos produtos"""
        from tqdm import tqdm
        
        resultados = []
        for produto in tqdm(produtos, desc="Classificando"):
            resultado = self.classificar(produto, usar_ia=usar_ia)
            resultados.append(resultado)
        
        return resultados


# Instância global
_classificador_global: Optional[ClassificadorNCM] = None

def get_classificador() -> ClassificadorNCM:
    """Retorna instância global do classificador"""
    global _classificador_global
    if _classificador_global is None:
        _classificador_global = ClassificadorNCM()
        _classificador_global.inicializar()
    return _classificador_global


if __name__ == "__main__":
    # Teste interativo
    classificador = ClassificadorNCM()
    classificador.inicializar()
    
    print("\n" + "="*60)
    print("🦈 SHARKIA - CLASSIFICADOR NCM")
    print("="*60)
    
    produtos_teste = [
        "Monitor LED Dell 24 polegadas Full HD",
        "Notebook Lenovo ThinkPad i7 16GB RAM",
        "Carne bovina congelada sem osso",
        "Parafuso de aço inoxidável M8",
        "Smartphone Samsung Galaxy S24 Ultra",
    ]
    
    for produto in produtos_teste:
        print(f"\n📦 Produto: {produto}")
        print("-"*50)
        
        resultado = classificador.classificar(produto)
        
        if resultado['sucesso']:
            print(f"✅ NCM: {resultado['ncm_codigo']}")
            print(f"   Descrição: {resultado['ncm_descricao']}")
            print(f"   Confiança: {resultado['confianca']}")
            print(f"   Método: {resultado['metodo']}")
            if resultado.get('justificativa'):
                print(f"   Justificativa: {resultado['justificativa']}")
        else:
            print(f"❌ Erro: {resultado.get('erro')}")
