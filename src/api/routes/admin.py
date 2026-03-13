"""
Rotas Administrativas - cache, delete classificações, status
"""
from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas import DeletarClassificacaoRequest
from src.api.deps import get_usuario_id
from src.data.database import (
    deletar_classificacao,
    deletar_classificacoes_por_produto,
)

router = APIRouter(tags=["Admin"])


@router.delete("/classificacao/{registro_id}")
async def deletar_classificacao_por_id(
    registro_id: str,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Deleta uma classificação específica pelo ID (global).
    Requer header **X-User-Token**.
    """
    try:
        deletado = deletar_classificacao(registro_id)
        if not deletado:
            raise HTTPException(status_code=404, detail="Classificação não encontrada")

        return {
            "sucesso": True,
            "mensagem": f"Classificação {registro_id} deletada com sucesso"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/classificacoes/produto")
async def deletar_classificacoes_produto(
    request: DeletarClassificacaoRequest,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Deleta classificações de um produto (global).
    Requer header **X-User-Token**.
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


@router.get("/cache/estatisticas")
async def estatisticas_cache(
    usuario_id: str = Depends(get_usuario_id),
):
    """Retorna estatísticas do cache de respostas da IA"""
    try:
        from src.data.database import estatisticas_cache_ia
        stats = estatisticas_cache_ia()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/limpar")
async def limpar_cache(
    dias: int = 30,
    usuario_id: str = Depends(get_usuario_id),
):
    """Limpa entradas antigas do cache de IA"""
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
