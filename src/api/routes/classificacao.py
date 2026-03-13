"""
Rota de Classificação - POST /classificar
"""
from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas import ProdutoRequest, ClassificacaoResponse
from src.api.deps import get_usuario_id, get_busca, get_classificador
from src.data.database import (
    criar_pesquisa_pendente,
    normalizar_ncm,
    buscar_ncms_por_historico,
    buscar_ncms_por_produto_exato,
    buscar_descartes_produto,
)

router = APIRouter(tags=["Classificação"])


@router.post("/classificar", response_model=ClassificacaoResponse)
async def classificar_produto(
    request: ProdutoRequest,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Classifica um produto e retorna opções de NCM priorizadas

    **Priorização:**
    1. NCMs do histórico com produto EXATO (mais usos primeiro)
    2. NCMs do histórico com produto SIMILAR (mais usos primeiro)
    3. NCMs sugeridos pela IA (se necessário para completar top_k)

    Requer header **X-User-Token** com o ID do usuário.
    """
    try:
        opcoes_finais = []
        ncms_usados = set()
        metodo = "historico"
        justificativa = ""

        # ====== 0. BUSCAR NCMs DESCARTADOS PARA ESTE PRODUTO ======
        ncms_descartados = set(buscar_descartes_produto(request.produto))

        # ====== 0.1 FAZER BUSCA SEMÂNTICA PARA OBTER SCORES DE MATCH ======
        busca = get_busca()
        resultados_semanticos = busca.buscar(request.produto, top_k=50)
        scores_match_cache = {}
        for r in resultados_semanticos:
            ncm_limpo = normalizar_ncm(r.get('codigo', ''))
            if ncm_limpo:
                scores_match_cache[ncm_limpo] = r.get('score', 0.0)

        # ====== 1. BUSCAR NO HISTÓRICO (PRODUTO EXATO) ======
        historico_exato = buscar_ncms_por_produto_exato(request.produto, limite=request.top_k)

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

        total_usos_exato = sum(i['usos'] for i in itens_historico_exato)

        for item in itens_historico_exato:
            score_usos = item['usos'] / total_usos_exato if total_usos_exato > 0 else 0.0
            score_match_salvo = item.get('score_match_salvo', 0.0)
            score_match_c = scores_match_cache.get(item['ncm'], 0.0)
            score_match = max(score_match_salvo, score_match_c)

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

            total_usos_similar = sum(i['usos'] for i in itens_historico_similar)

            for item in itens_historico_similar:
                score_usos = item['usos'] / total_usos_similar if total_usos_similar > 0 else 0.0
                score_match_salvo = item.get('score_match_salvo', 0.0)
                score_match_c = scores_match_cache.get(item['ncm'], 0.0)
                score_match = max(score_match_salvo, score_match_c)

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
                top_k=request.top_k * 2,
                salvar_historico=False,
                pular_historico=True
            )

            if resultado.get('sucesso'):
                if len(opcoes_finais) > 0:
                    metodo = "historico_ia"
                    justificativa = f"Histórico: {len(opcoes_finais)} opção(ões), completado com IA"
                else:
                    metodo = resultado.get('metodo', 'ia')
                    justificativa = resultado.get('justificativa', '')

                ncm_ia = resultado.get('ncm_codigo')
                if ncm_ia:
                    ncm_ia_limpo = normalizar_ncm(ncm_ia)
                    if ncm_ia_limpo and ncm_ia_limpo not in ncms_usados and ncm_ia_limpo not in ncms_descartados:
                        ncms_usados.add(ncm_ia_limpo)
                        opcoes_finais.append({
                            'ncm': ncm_ia_limpo,
                            'descricao': resultado.get('ncm_descricao', ''),
                            'score_match': 0.95,
                            'score_match_percentual': '95.0%',
                            'score_usos': 0.0,
                            'score_usos_percentual': 'N/A',
                            'usos': 0,
                            'fonte': 'ia'
                        })

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
            metodo = "historico"
            justificativa = f"Encontrado no histórico com {len(opcoes_finais)} classificações anteriores"

        if len(opcoes_finais) == 0:
            raise HTTPException(status_code=404, detail="Nenhum NCM encontrado para este produto")

        opcoes_finais = opcoes_finais[:request.top_k]

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
