"""
Rota de Confirmação - POST /confirmar + GET /pendentes
"""
from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas import ConfirmarRequest, ConfirmacaoResponse
from src.api.deps import get_usuario_id
from src.data.database import (
    confirmar_pesquisa,
    listar_pesquisas_pendentes,
    limpar_pesquisas_expiradas,
    inserir_classificacao_usuario,
)

router = APIRouter(tags=["Confirmação"])


@router.post("/confirmar", response_model=ConfirmacaoResponse)
async def confirmar_classificacao(
    request: ConfirmarRequest,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Confirma qual opção de NCM é a correta e salva no banco.

    - Salva no registro **global** (histórico de aprendizado).
    - Salva também no registro **do usuário** para consulta posterior.

    Requer header **X-User-Token**.
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

        # Salvar na tabela do usuário
        inserir_classificacao_usuario(
            usuario_id=usuario_id,
            classificacao_id=resultado.get('id', ''),
            produto=resultado.get('produto', ''),
            ncm_codigo=resultado.get('ncm_codigo', ''),
            ncm_descricao=resultado.get('ncm_descricao', ''),
            score_match=resultado.get('score_match', 0.0),
            metodo=resultado.get('metodo', ''),
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


@router.get("/pendentes")
async def listar_pendentes(
    limite: int = 50,
    usuario_id: str = Depends(get_usuario_id),
):
    """Lista pesquisas pendentes (não confirmadas)"""
    try:
        limpar_pesquisas_expiradas()
        pendentes = listar_pesquisas_pendentes(limite)
        return {
            "total": len(pendentes),
            "pesquisas": pendentes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
