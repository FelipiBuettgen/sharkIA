"""
API REST - SharkIA Classificador NCM
"""
import os
import sys

# Forcar UTF-8 no stdout/stderr para suportar emojis no Windows (cp1252)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

print("🦈 SharkIA - Iniciando importações...")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

print("📦 Importando módulo de banco de dados...")

# Importar funções de banco de dados (o módulo auto-inicializa)
from src.data.database import (
    criar_pesquisa_pendente,
    confirmar_pesquisa,
    buscar_pesquisa_pendente,
    listar_pesquisas_pendentes,
    limpar_pesquisas_expiradas,
    normalizar_ncm,
    formatar_ncm,
    buscar_ncms_por_historico,
    buscar_ncms_por_produto_exato,
    registrar_descarte,
    buscar_descartes_produto,
    estatisticas_descartes,
    deletar_classificacao,
    deletar_classificacoes_por_produto
)

print("✅ Banco de dados importado!")

app = FastAPI(
    title="🦈 SharkIA - Classificador NCM",
    description="API inteligente para classificação de produtos em códigos NCM",
    version="2.0.0"
)

print("✅ FastAPI app criado!")

# CORS para acesso do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Startup/Shutdown ====================

# Flag para indicar se o sistema está totalmente pronto
_sistema_pronto = False

@app.on_event("startup")
async def startup_event():
    """
    Pré-carrega modelos e sistemas no startup da API.
    O banco já foi inicializado no import. Carregamento de modelos
    é feito em background para não bloquear o healthcheck.
    """
    import asyncio
    print("\n🚀 API iniciando...")
    
    # Iniciar carregamento de modelos em background (não bloqueia healthcheck)
    try:
        asyncio.create_task(_carregar_modelos_background())
        print("✅ API pronta - modelos carregando em background...\n")
    except Exception as e:
        print(f"⚠️ Erro ao criar task de carregamento: {e}")
        print("✅ API pronta - modelos serão carregados sob demanda\n")


async def _carregar_modelos_background():
    """Carrega modelos em background para não bloquear startup"""
    import asyncio
    global _sistema_pronto
    
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _precarregar_sistemas)
        _sistema_pronto = True
        print("✅ Todos os modelos carregados em background!")
    except Exception as e:
        print(f"⚠️ Erro no carregamento de modelos: {e}")
        # Sistemas serão carregados on-demand se necessário


def _precarregar_sistemas():
    """Função síncrona para pré-carregamento"""
    try:
        # 1. Carregar busca semântica (modelo de embeddings)
        print("⏳ Carregando busca semântica...")
        _ = get_busca()
        print("✅ Busca semântica carregada")
        
        # 2. Carregar classificador (reutiliza busca + configura IA)
        print("⏳ Carregando classificador...")
        _ = get_classificador()
        print("✅ Classificador carregado")
        
        print("✅ Todos os sistemas pré-carregados!")
    except Exception as e:
        print(f"⚠️ Erro no pré-carregamento: {e}")
        # Não re-raise - permite que a API inicie e carregue sob demanda


# Modelos de request/response
class ProdutoRequest(BaseModel):
    produto: str = Field(..., description="Descrição do produto", example="Monitor LED Dell 24 polegadas")
    top_k: int = Field(10, description="Número de candidatos para busca", ge=1, le=50)

class ConfirmarRequest(BaseModel):
    pesquisa_id: str = Field(..., description="ID da pesquisa retornado no /classificar")
    opcao_id: str = Field(..., description="ID da opção escolhida como correta")

class LoteRequest(BaseModel):
    produtos: List[str] = Field(..., description="Lista de produtos")

class OpcaoNCM(BaseModel):
    id: str = Field(..., description="ID único desta opção")
    ncm: str = Field(..., description="Código NCM (sem pontos)")
    descricao: str = Field(..., description="Descrição do NCM")
    score_match: float = Field(0.0, description="Score de similaridade semântica da IA (0 a 1)")
    score_match_percentual: str = Field("N/A", description="Score de match em porcentagem")
    score_usos: float = Field(0.0, description="Score baseado na proporção de usos (0 a 1)")
    score_usos_percentual: str = Field("N/A", description="Proporção de usos em porcentagem")
    usos: int = Field(0, description="Quantas vezes este NCM foi usado para este produto")
    fonte: str = Field("ia", description="Origem: 'historico', 'historico_exato' ou 'ia'")

class ClassificacaoResponse(BaseModel):
    sucesso: bool
    pesquisa_id: str = Field(..., description="ID da pesquisa (usar para confirmar)")
    produto: str
    opcoes: List[OpcaoNCM] = Field(..., description="3 opções de NCM para escolher")
    metodo: Optional[str] = None
    justificativa: Optional[str] = None
    expira_em: Optional[str] = None
    erro: Optional[str] = None

class ConfirmacaoResponse(BaseModel):
    sucesso: bool
    mensagem: str
    ncm: Optional[str] = None
    descricao: Optional[str] = None

class BuscaRequest(BaseModel):
    query: str = Field(..., description="Texto de busca")
    top_k: int = Field(10, description="Número de resultados", ge=1, le=50)


# Estado global
_classificador = None
_busca = None

def get_busca():
    """Singleton para BuscaSemantica - carrega apenas uma vez"""
    global _busca
    if _busca is None:
        from src.search.semantic_search import BuscaSemantica
        _busca = BuscaSemantica()
        _busca.carregar()
    return _busca

def get_classificador():
    """Singleton para ClassificadorNCM - reutiliza a busca já carregada"""
    global _classificador
    if _classificador is None:
        from src.classification.classifier import ClassificadorNCM
        # Passa a busca já carregada para evitar carregar o modelo 2x
        _classificador = ClassificadorNCM(busca_externa=get_busca())
        _classificador.inicializar()
    return _classificador


@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "titulo": "SharkIA - Classificador NCM",
        "versao": "2.0.0",
        "fluxo": "1. POST /classificar -> 2. POST /confirmar",
        "endpoints": {
            "classificar": "POST /classificar - Retorna 3 opções de NCM",
            "confirmar": "POST /confirmar - Confirma a opção correta e salva",
            "buscar": "POST /buscar - Busca semântica (sem salvar)",
            "pendentes": "GET /pendentes - Lista pesquisas não confirmadas",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health():
    """Verifica saúde da API"""
    return {
        "status": "ok", 
        "servico": "sharkia", 
        "versao": "2.0.0",
        "modelos_carregados": _sistema_pronto
    }


@app.get("/status")
async def status():
    """Retorna status completo do sistema incluindo rate limits"""
    try:
        from src.utils.rate_limiter import status_limites
        from src.data.learning import estatisticas_historico
        
        return {
            "servico": "sharkia",
            "versao": "2.0.0",
            "rate_limits": status_limites(),
            "historico": estatisticas_historico()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classificar", response_model=ClassificacaoResponse)
async def classificar_produto(request: ProdutoRequest):
    """
    Classifica um produto e retorna opções de NCM priorizadas
    
    **Priorização:**
    1. NCMs do histórico com produto EXATO (mais usos primeiro)
    2. NCMs do histórico com produto SIMILAR (mais usos primeiro)
    3. NCMs sugeridos pela IA (se necessário para completar top_k)
    
    - **produto**: Descrição do produto
    - **top_k**: Número de opções a retornar (default: 3)
    
    **Retorna:** pesquisa_id + opções de NCM ordenadas por relevância
    """
    try:
        opcoes_finais = []
        ncms_usados = set()  # Para evitar duplicatas
        metodo = "historico"
        justificativa = ""
        
        # ====== 0. BUSCAR NCMs DESCARTADOS PARA ESTE PRODUTO ======
        ncms_descartados = set(buscar_descartes_produto(request.produto))
        
        # ====== 0.1 FAZER BUSCA SEMÂNTICA PARA OBTER SCORES DE MATCH ======
        busca = get_busca()
        resultados_semanticos = busca.buscar(request.produto, top_k=50)  # Buscar mais para ter cache
        scores_match_cache = {}
        for r in resultados_semanticos:
            ncm_limpo = normalizar_ncm(r.get('codigo', ''))
            if ncm_limpo:
                scores_match_cache[ncm_limpo] = r.get('score', 0.0)
        
        # ====== 1. BUSCAR NO HISTÓRICO (PRODUTO EXATO) ======
        historico_exato = buscar_ncms_por_produto_exato(request.produto, limite=request.top_k)
        
        # Coletar itens válidos do histórico exato
        itens_historico_exato = []
        for item in historico_exato:
            ncm = item['ncm']
            if ncm and ncm not in ncms_usados and ncm not in ncms_descartados:
                ncms_usados.add(ncm)
                itens_historico_exato.append({
                    'ncm': ncm,
                    'descricao': item['descricao'],
                    'usos': item['usos'],
                    'score_match_salvo': item.get('score_match', 0.0),
                    'fonte': 'historico_exato'
                })
                if len(itens_historico_exato) >= request.top_k:
                    break
        
        # Calcular total de usos para score proporcional
        total_usos_exato = sum(i['usos'] for i in itens_historico_exato)
        
        for item in itens_historico_exato:
            # Score usos = proporção de usos (ex: 2 de 3 = 66.6%)
            if total_usos_exato > 0:
                score_usos = item['usos'] / total_usos_exato
            else:
                score_usos = 0.0
            
            # Score match = valor salvo no histórico ou do cache semântico
            score_match_salvo = item.get('score_match_salvo', 0.0)
            score_match_cache = scores_match_cache.get(item['ncm'], 0.0)
            # Usar o maior entre salvo e cache (cache pode ter valor mais atualizado)
            score_match = max(score_match_salvo, score_match_cache)
            
            opcoes_finais.append({
                'ncm': item['ncm'],
                'descricao': item['descricao'],
                'score_match': score_match,
                'score_match_percentual': f"{score_match * 100:.1f}%" if score_match > 0 else "N/A",
                'score_usos': score_usos,
                'score_usos_percentual': f"{score_usos * 100:.1f}%",
                'usos': item['usos'],
                'fonte': item['fonte']
            })
        
        # ====== 2. BUSCAR NO HISTÓRICO (PRODUTO SIMILAR) ======
        if len(opcoes_finais) < request.top_k:
            historico_similar = buscar_ncms_por_historico(request.produto, limite=request.top_k)
            
            # Coletar itens válidos do histórico similar
            itens_historico_similar = []
            for item in historico_similar:
                ncm = item['ncm']
                if ncm and ncm not in ncms_usados and ncm not in ncms_descartados:
                    ncms_usados.add(ncm)
                    itens_historico_similar.append({
                        'ncm': ncm,
                        'descricao': item['descricao'],
                        'usos': item['usos'],
                        'score_match_salvo': item.get('score_match', 0.0),
                        'fonte': 'historico'
                    })
                    if len(opcoes_finais) + len(itens_historico_similar) >= request.top_k:
                        break
            
            # Calcular total de usos para score proporcional
            total_usos_similar = sum(i['usos'] for i in itens_historico_similar)
            
            for item in itens_historico_similar:
                if total_usos_similar > 0:
                    score_usos = item['usos'] / total_usos_similar
                else:
                    score_usos = 0.0
                
                # Score match = valor salvo no histórico ou do cache semântico
                score_match_salvo = item.get('score_match_salvo', 0.0)
                score_match_cache = scores_match_cache.get(item['ncm'], 0.0)
                score_match = max(score_match_salvo, score_match_cache)
                
                opcoes_finais.append({
                    'ncm': item['ncm'],
                    'descricao': item['descricao'],
                    'score_match': score_match,
                    'score_match_percentual': f"{score_match * 100:.1f}%" if score_match > 0 else "N/A",
                    'score_usos': score_usos,
                    'score_usos_percentual': f"{score_usos * 100:.1f}%",
                    'usos': item['usos'],
                    'fonte': item['fonte']
                })
        
        # ====== 3. COMPLETAR COM IA (se necessário) ======
        if len(opcoes_finais) < request.top_k:
            classificador = get_classificador()
            
            resultado = classificador.classificar(
                produto=request.produto,
                usar_ia=True,
                top_k=request.top_k * 2,  # Buscar mais para ter opções após filtrar duplicatas
                salvar_historico=False,
                pular_historico=True  # Já verificamos o histórico, queremos IA
            )
            
            if resultado.get('sucesso'):
                # Se já temos itens do histórico, o método é misto
                if len(opcoes_finais) > 0:
                    metodo = "historico_ia"
                    justificativa = f"Histórico: {len(opcoes_finais)} opção(ões), completado com IA"
                else:
                    metodo = resultado.get('metodo', 'ia')
                    justificativa = resultado.get('justificativa', '')
                
                # Primeiro adicionar o NCM sugerido pela IA (se houver e não descartado)
                ncm_ia = resultado.get('ncm_codigo')
                if ncm_ia:
                    ncm_ia_limpo = normalizar_ncm(ncm_ia)
                    if ncm_ia_limpo and ncm_ia_limpo not in ncms_usados and ncm_ia_limpo not in ncms_descartados:
                        ncms_usados.add(ncm_ia_limpo)
                        opcoes_finais.append({
                            'ncm': ncm_ia_limpo,
                            'descricao': resultado.get('ncm_descricao', ''),
                            'score_match': 0.95,  # Alta confiança por ser sugestão direta da IA
                            'score_match_percentual': '95.0%',
                            'score_usos': 0.0,
                            'score_usos_percentual': 'N/A',
                            'usos': 0,
                            'fonte': 'ia'
                        })
                
                # Depois adicionar candidatos da busca semântica (filtrar descartados)
                candidatos = resultado.get('candidatos', [])
                for c in candidatos:
                    if len(opcoes_finais) >= request.top_k:
                        break
                    
                    ncm = normalizar_ncm(c.get('codigo', ''))
                    if ncm and ncm not in ncms_usados and ncm not in ncms_descartados:
                        ncms_usados.add(ncm)
                        opcoes_finais.append({
                            'ncm': ncm,
                            'descricao': c.get('descricao', ''),
                            'score_match': c.get('score', 0.0),
                            'score_match_percentual': f"{c.get('score', 0.0) * 100:.1f}%",
                            'score_usos': 0.0,
                            'score_usos_percentual': 'N/A',
                            'usos': 0,
                            'fonte': 'ia'
                        })
        else:
            # Se não usou IA, atualizar metodo
            metodo = "historico"
            justificativa = f"Encontrado no histórico com {len(opcoes_finais)} classificações anteriores"
        
        # ====== GARANTIR MÍNIMO DE OPÇÕES ======
        if len(opcoes_finais) == 0:
            raise HTTPException(status_code=404, detail="Nenhum NCM encontrado para este produto")
        
        # Limitar ao top_k (não preenche com vazios - retorna apenas opções válidas)
        opcoes_finais = opcoes_finais[:request.top_k]
        
        # ====== CRIAR PESQUISA PENDENTE ======
        pesquisa = criar_pesquisa_pendente(
            produto=request.produto,
            opcoes=opcoes_finais,
            metodo=metodo,
            justificativa=justificativa
        )
        
        return {
            "sucesso": True,
            "pesquisa_id": pesquisa['pesquisa_id'],
            "produto": request.produto,
            "opcoes": pesquisa['opcoes'],
            "metodo": metodo,
            "justificativa": justificativa,
            "expira_em": pesquisa['expira_em']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/confirmar", response_model=ConfirmacaoResponse)
async def confirmar_classificacao(request: ConfirmarRequest):
    """
    Confirma qual opção de NCM é a correta e salva no banco
    
    - **pesquisa_id**: ID retornado pelo /classificar
    - **opcao_id**: ID da opção escolhida como correta
    
    **Após confirmar:** A classificação é salva no histórico para aprendizado
    """
    try:
        resultado = confirmar_pesquisa(
            pesquisa_id=request.pesquisa_id,
            opcao_id=request.opcao_id
        )
        
        if resultado is None:
            raise HTTPException(
                status_code=404, 
                detail="Pesquisa não encontrada ou já confirmada. Verifique pesquisa_id e opcao_id."
            )
        
        return {
            "sucesso": True,
            "mensagem": "Classificação confirmada e salva com sucesso",
            "ncm": resultado.get('ncm_codigo'),
            "descricao": resultado.get('ncm_descricao')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pendentes")
async def listar_pendentes(limite: int = 50):
    """
    Lista pesquisas pendentes (não confirmadas)
    """
    try:
        # Limpar expiradas primeiro
        limpar_pesquisas_expiradas()
        
        pendentes = listar_pesquisas_pendentes(limite)
        return {
            "total": len(pendentes),
            "pesquisas": pendentes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/buscar")
async def buscar_ncm(request: BuscaRequest):
    """
    Busca semântica de NCMs (sem salvar, sem IA)
    
    - **query**: Texto de busca
    - **top_k**: Número de resultados
    
    **Retorna:** Lista de NCMs com score (sem pontos)
    """
    try:
        busca = get_busca()
        resultados = busca.buscar(request.query, top_k=request.top_k)
        
        # Normalizar NCMs (remover pontos)
        for r in resultados:
            r['ncm'] = normalizar_ncm(r.get('codigo', ''))
            r['codigo_formatado'] = r.get('codigo', '')  # Mantém original como referência
            del r['codigo']  # Remove campo antigo
        
        return {
            "query": request.query,
            "total": len(resultados),
            "resultados": resultados
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ncm/{codigo}")
async def consultar_ncm(codigo: str):
    """
    Consulta informações de um NCM específico
    
    - **codigo**: NCM com ou sem pontos (ex: "02013000" ou "0201.30.00")
    
    Busca dados diretamente do banco de dados, incluindo termos aprendidos.
    """
    try:
        from src.data.database import buscar_ncm, normalizar_ncm
        
        codigo_limpo = normalizar_ncm(codigo)
        
        # Buscar no banco de dados
        ncm = buscar_ncm(codigo_limpo)
        
        if ncm:
            # Formatar resposta
            return {
                "ncm": ncm['codigo'],
                "codigo_formatado": ncm.get('codigo_formatado', ncm['codigo']),
                "descricao": ncm.get('descricao', ''),
                "capitulo": ncm.get('capitulo', ''),
                "posicao": ncm.get('posicao', ''),
                "termos_aprendidos": ncm.get('termos_aprendidos', []),
                "total_termos": ncm.get('total_termos', 0),
                "data_inicio": ncm.get('data_inicio', ''),
                "data_fim": ncm.get('data_fim', '')
            }
        
        # Fallback: buscar no sistema de busca semântica (JSON)
        busca = get_busca()
        for ncm_item in busca.ncms:
            ncm_limpo = normalizar_ncm(ncm_item.get('codigo', ''))
            if ncm_limpo == codigo_limpo:
                resultado = ncm_item.copy()
                resultado['ncm'] = ncm_limpo
                resultado['codigo_formatado'] = ncm_item.get('codigo', '')
                resultado['termos_aprendidos'] = resultado.get('termos_aprendidos', [])
                resultado['total_termos'] = len(resultado['termos_aprendidos'])
                return resultado
        
        raise HTTPException(status_code=404, detail=f"NCM {codigo} não encontrado")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _buscar_termos_aprendidos_ncm(ncm_codigo: str) -> list:
    """Busca produtos únicos classificados para um NCM no histórico"""
    try:
        from src.data.database import get_connection, normalizar_ncm
        
        ncm_normalizado = normalizar_ncm(ncm_codigo)
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT produto 
                FROM classificacoes 
                WHERE ncm_codigo = ? 
                AND (validado_usuario = 1 OR confianca = 'alta')
                ORDER BY produto
            """, (ncm_normalizado,))
            
            termos = [row['produto'] for row in cursor.fetchall()]
            return termos
    except Exception:
        return []


# ============================================================
# ENDPOINTS DE APRENDIZADO
# ============================================================

class ValidacaoRequest(BaseModel):
    registro_id: str = Field(..., description="ID do registro a validar")
    correto: bool = Field(..., description="Se a classificação estava correta")
    ncm_correto: Optional[str] = Field(None, description="NCM correto se o original estava errado")


@app.get("/aprendizado/estatisticas")
async def estatisticas_aprendizado():
    """
    Retorna estatísticas do sistema de aprendizado
    """
    try:
        from src.data.learning import estatisticas_historico
        stats = estatisticas_historico()
        return {
            "historico": stats,
            "mensagem": f"Sistema tem {stats.get('prontos_treinamento', 0)} registros prontos para treino"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/aprendizado/historico")
async def listar_historico(limit: int = 50):
    """
    Lista últimas classificações do histórico
    """
    try:
        from src.data.learning import carregar_historico
        historico = carregar_historico()
        return {
            "total": len(historico),
            "registros": historico[-limit:][::-1]  # Últimos primeiro
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/aprendizado/validar")
async def validar_classificacao(request: ValidacaoRequest):
    """
    Valida uma classificação (feedback do usuário)
    
    - **registro_id**: ID do registro no histórico
    - **correto**: True se a classificação estava correta
    - **ncm_correto**: NCM correto sem pontos (só se correto=False)
    """
    try:
        from src.data.learning import validar_classificacao
        
        # Normalizar NCM corrigido se fornecido
        ncm_corrigido = None
        if request.ncm_correto:
            ncm_corrigido = normalizar_ncm(request.ncm_correto)
        
        validar_classificacao(
            registro_id=request.registro_id,
            correto=request.correto,
            ncm_correto=ncm_corrigido
        )
        return {"sucesso": True, "mensagem": "Validação registrada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/aprendizado/retreinar")
async def retreinar_modelo():
    """
    Re-treina o modelo com dados aprendidos do histórico
    
    ATENÇÃO: Este processo pode levar alguns minutos.
    A API ficará indisponível durante o re-treinamento.
    """
    try:
        from src.data.retrain import retreinar_completo
        retreinar_completo()
        
        # Limpa cache para forçar reload
        global _classificador, _busca
        _classificador = None
        _busca = None
        
        return {
            "sucesso": True,
            "mensagem": "Modelo re-treinado com sucesso! Agora usando dados aprendidos."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS DE DESCARTE
# ============================================================

class DescarteRequest(BaseModel):
    pesquisa_id: str = Field(..., description="ID da pesquisa")
    opcao_id: str = Field(..., description="ID da opção a descartar")
    motivo: Optional[str] = Field("", description="Motivo do descarte (opcional)")


class DescarteResponse(BaseModel):
    sucesso: bool
    mensagem: str
    ncm: Optional[str] = None
    contador: Optional[int] = None


@app.post("/descartar", response_model=DescarteResponse)
async def descartar_opcao(request: DescarteRequest):
    """
    Descarta uma opção de NCM para um produto.
    
    Opções descartadas não aparecem mais nas próximas buscas para o mesmo produto.
    Se descartada múltiplas vezes, também deixa de aparecer para produtos similares.
    
    - **pesquisa_id**: ID da pesquisa
    - **opcao_id**: ID da opção a descartar
    - **motivo**: Descrição do motivo (ex: "NCM não relacionado")
    """
    try:
        # Buscar a pesquisa pendente
        pesquisa = buscar_pesquisa_pendente(request.pesquisa_id)
        
        if not pesquisa:
            raise HTTPException(
                status_code=404,
                detail="Pesquisa não encontrada ou já confirmada"
            )
        
        # Encontrar a opção pelo ID
        ncm_encontrado = None
        produto = pesquisa['produto']
        
        # Verificar cada opção
        for i in range(1, 4):
            opcao_id = pesquisa.get(f'opcao{i}_id')
            if opcao_id == request.opcao_id:
                ncm_encontrado = pesquisa.get(f'opcao{i}_ncm')
                break
        
        if not ncm_encontrado:
            raise HTTPException(
                status_code=404,
                detail="Opção não encontrada nesta pesquisa"
            )
        
        # Registrar o descarte
        resultado = registrar_descarte(
            produto=produto,
            ncm_codigo=ncm_encontrado,
            motivo=request.motivo
        )
        
        return {
            "sucesso": True,
            "mensagem": resultado['mensagem'],
            "ncm": resultado['ncm'],
            "contador": resultado['contador']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/descartes/estatisticas")
async def estatisticas_de_descartes():
    """
    Retorna estatísticas do sistema de descartes
    """
    try:
        stats = estatisticas_descartes()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Deletar Classificações ====================

class DeletarClassificacaoRequest(BaseModel):
    produto: str = Field(..., description="Descrição exata do produto")
    ncm: Optional[str] = Field(None, description="NCM específico (se não informado, deleta todos do produto)")


@app.delete("/classificacao/{registro_id}")
async def deletar_classificacao_por_id(registro_id: str):
    """
    Deleta uma classificação específica pelo ID
    
    Use para remover uma sugestão acatada incorretamente.
    """
    try:
        deletado = deletar_classificacao(registro_id)
        
        if not deletado:
            raise HTTPException(
                status_code=404,
                detail="Classificação não encontrada"
            )
        
        return {
            "sucesso": True,
            "mensagem": f"Classificação {registro_id} deletada com sucesso"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/classificacoes/produto")
async def deletar_classificacoes_produto(request: DeletarClassificacaoRequest):
    """
    Deleta classificações de um produto
    
    - Se informar apenas `produto`: deleta TODAS as classificações desse produto
    - Se informar `produto` + `ncm`: deleta apenas a combinação específica
    
    Use para limpar sugestões acatadas incorretamente.
    """
    try:
        quantidade = deletar_classificacoes_por_produto(
            produto=request.produto,
            ncm_codigo=request.ncm
        )
        
        if quantidade == 0:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma classificação encontrada para este produto/NCM"
            )
        
        return {
            "sucesso": True,
            "mensagem": f"{quantidade} classificação(ões) deletada(s)",
            "produto": request.produto,
            "ncm": request.ncm,
            "quantidade_deletada": quantidade
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Validação de NCM ====================

@app.get("/validar/{ncm}")
async def validar_ncm(ncm: str):
    """
    Valida se um NCM existe na tabela oficial.
    
    Retorna informações do NCM se for válido.
    """
    try:
        busca = get_busca()
        
        # Normalizar NCM (remover pontos)
        ncm_normalizado = normalizar_ncm(ncm)
        
        # Buscar na lista de NCMs carregados
        ncm_encontrado = next(
            (n for n in busca.ncms if normalizar_ncm(n.get('codigo', '')) == ncm_normalizado),
            None
        )
        
        if ncm_encontrado:
            return {
                "valido": True,
                "ncm": ncm_normalizado,
                "ncm_formatado": formatar_ncm(ncm_normalizado),
                "descricao": ncm_encontrado.get('descricao', ''),
                "capitulo": ncm_normalizado[:2] if len(ncm_normalizado) >= 2 else None
            }
        else:
            return {
                "valido": False,
                "ncm": ncm_normalizado,
                "mensagem": "NCM não encontrado na tabela oficial"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Estatísticas do Cache ====================

@app.get("/cache/estatisticas")
async def estatisticas_cache():
    """
    Retorna estatísticas do cache de respostas da IA.
    """
    try:
        from src.data.database import estatisticas_cache_ia
        stats = estatisticas_cache_ia()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache/limpar")
async def limpar_cache(dias: int = 30):
    """
    Limpa entradas antigas do cache de IA.
    
    Args:
        dias: Remove entradas mais antigas que N dias (default: 30)
    """
    try:
        from src.data.database import limpar_cache_ia
        removidos = limpar_cache_ia(dias)
        return {
            "sucesso": True,
            "mensagem": f"{removidos} entradas removidas do cache",
            "dias_limite": dias
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
