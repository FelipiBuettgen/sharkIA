"""
Rotas de Descarte - POST /descartar, GET /descartes/estatisticas
"""
from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas import DescarteRequest, DescarteResponse
from src.api.deps import get_usuario_id
from src.data.database import (
    buscar_pesquisa_pendente,
    registrar_descarte,
    estatisticas_descartes,
    registrar_descarte_usuario,
)

router = APIRouter(tags=["Descartes"])


@router.post("/descartar", response_model=DescarteResponse)
async def descartar_opcao(
    request: DescarteRequest,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Descarta uma opção de NCM para um produto.

    - Salva no descarte **global** e no descarte **do usuário**.
    - Opções descartadas não aparecem mais nas próximas buscas para o mesmo produto.

    Requer header **X-User-Token**.
    """
    try:
        pesquisa = buscar_pesquisa_pendente(request.pesquisa_id)

        if not pesquisa:
            raise HTTPException(
                status_code=404,
                detail="Pesquisa não encontrada ou já confirmada"
            )

        ncm_encontrado = None
        produto = pesquisa['produto']

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

        # Registrar descarte global
        resultado = registrar_descarte(
            produto=produto,
            ncm_codigo=ncm_encontrado,
            motivo=request.motivo
        )

        # Registrar descarte do usuário
        registrar_descarte_usuario(
            usuario_id=usuario_id,
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


@router.get("/descartes/estatisticas")
async def estatisticas_de_descartes(
    usuario_id: str = Depends(get_usuario_id),
):
    """Retorna estatísticas do sistema de descartes (global)"""
    try:
        stats = estatisticas_descartes()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
