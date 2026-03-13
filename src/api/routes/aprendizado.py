"""
Rotas de Aprendizado - /aprendizado/*
"""
from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas import ValidacaoRequest
from src.api.deps import get_usuario_id, reset_modelos
from src.data.database import normalizar_ncm

router = APIRouter(prefix="/aprendizado", tags=["Aprendizado"])


@router.get("/estatisticas")
async def estatisticas_aprendizado(
    usuario_id: str = Depends(get_usuario_id),
):
    """Retorna estatísticas do sistema de aprendizado"""
    try:
        from src.data.learning import estatisticas_historico
        stats = estatisticas_historico()
        return {
            "historico": stats,
            "mensagem": f"Sistema tem {stats.get('prontos_treinamento', 0)} registros prontos para treino"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historico")
async def listar_historico(
    limit: int = 50,
    usuario_id: str = Depends(get_usuario_id),
):
    """Lista últimas classificações do histórico global"""
    try:
        from src.data.learning import carregar_historico
        historico = carregar_historico()
        return {
            "total": len(historico),
            "registros": historico[-limit:][::-1]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validar")
async def validar_classificacao(
    request: ValidacaoRequest,
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Valida uma classificação (feedback do usuário).
    Requer header **X-User-Token**.
    """
    try:
        from src.data.learning import validar_classificacao as lrn_validar

        ncm_corrigido = None
        if request.ncm_correto:
            ncm_corrigido = normalizar_ncm(request.ncm_correto)

        lrn_validar(
            registro_id=request.registro_id,
            correto=request.correto,
            ncm_correto=ncm_corrigido
        )
        return {"sucesso": True, "mensagem": "Validação registrada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retreinar")
async def retreinar_modelo(
    usuario_id: str = Depends(get_usuario_id),
):
    """
    Re-treina o modelo com dados aprendidos do histórico.
    Requer header **X-User-Token**.
    """
    try:
        from src.data.retrain import retreinar_completo
        retreinar_completo()

        reset_modelos()

        return {
            "sucesso": True,
            "mensagem": "Modelo re-treinado com sucesso! Agora usando dados aprendidos."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
