"""
Rotas de Busca - POST /buscar, GET /ncm/{codigo}, GET /validar/{ncm}
"""
from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas import BuscaRequest
from src.api.deps import get_usuario_id, get_busca
from src.data.database import normalizar_ncm, formatar_ncm

router = APIRouter(tags=["Busca"])


@router.post("/buscar")
async def buscar_ncm(
    request: BuscaRequest,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Busca semântica de NCMs (sem salvar, sem IA).
    Requer header **X-User-Token**.
    """
    try:
        busca = get_busca()
        resultados = busca.buscar(request.query, top_k=request.top_k)

        for r in resultados:
            r['ncm'] = normalizar_ncm(r.get('codigo', ''))
            r['codigo_formatado'] = r.get('codigo', '')
            del r['codigo']

        return {
            "query": request.query,
            "total": len(resultados),
            "resultados": resultados
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ncm/{codigo}")
async def consultar_ncm(
    codigo: str,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Consulta informações de um NCM específico.
    Requer header **X-User-Token**.
    """
    try:
        from src.data.database import buscar_ncm as db_buscar_ncm

        codigo_limpo = normalizar_ncm(codigo)
        ncm = db_buscar_ncm(codigo_limpo)

        if ncm:
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

        # Fallback: buscar no sistema de busca semântica
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


@router.get("/validar/{ncm}")
async def validar_ncm(
    ncm: str,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Valida se um NCM existe na tabela oficial.
    Requer header **X-User-Token**.
    """
    try:
        busca = get_busca()
        ncm_normalizado = normalizar_ncm(ncm)

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
