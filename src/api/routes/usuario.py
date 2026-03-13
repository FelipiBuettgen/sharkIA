"""
Rotas do Usuário - classificações acatadas e descartes por usuário
"""
from fastapi import APIRouter, HTTPException, Depends

from src.api.deps import get_usuario_id
from src.data.database import (
    listar_classificacoes_usuario,
    listar_descartes_usuario,
    deletar_classificacao_usuario,
)

router = APIRouter(prefix="/usuario", tags=["Usuário"])


@router.get("/classificacoes")
async def minhas_classificacoes(
    limite: int = 100,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Retorna as classificações (sugestões acatadas) do usuário autenticado.

    Requer header **X-User-Token**.
    """
    try:
        registros = listar_classificacoes_usuario(usuario_id, limite)
        return {
            "usuario_id": usuario_id,
            "total": len(registros),
            "classificacoes": registros
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/descartes")
async def meus_descartes(
    limite: int = 100,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Retorna os descartes (sugestões rejeitadas) do usuário autenticado.

    Requer header **X-User-Token**.
    """
    try:
        registros = listar_descartes_usuario(usuario_id, limite)
        return {
            "usuario_id": usuario_id,
            "total": len(registros),
            "descartes": registros
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/classificacao/{classificacao_id}")
async def remover_classificacao_usuario(
    classificacao_id: str,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Remove uma classificação do registro pessoal do usuário.
    (Não remove do registro global.)

    Requer header **X-User-Token**.
    """
    try:
        removido = deletar_classificacao_usuario(usuario_id, classificacao_id)
        if not removido:
            raise HTTPException(status_code=404, detail="Classificação não encontrada para este usuário")
        return {"sucesso": True, "mensagem": "Classificação removida do seu registro"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
