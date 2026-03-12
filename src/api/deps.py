"""
Dependências compartilhadas - SharkIA API
Autenticação por token (user_id) e singletons de serviços.
"""
from fastapi import Header, HTTPException


# ==================== Autenticação ====================

async def get_usuario_id(x_user_token: str = Header(..., description="Token do usuário (ID do usuário)")) -> str:
    """
    Extrai o ID do usuário a partir do header X-User-Token.
    Todas as rotas recebem este header obrigatório.
    """
    if not x_user_token or not x_user_token.strip():
        raise HTTPException(status_code=401, detail="Token de usuário obrigatório (header X-User-Token)")
    return x_user_token.strip()


# ==================== Singletons ====================

_classificador = None
_busca = None
_sistema_pronto = False


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
        _classificador = ClassificadorNCM(busca_externa=get_busca())
        _classificador.inicializar()
    return _classificador


def set_sistema_pronto(valor: bool):
    global _sistema_pronto
    _sistema_pronto = valor


def is_sistema_pronto() -> bool:
    return _sistema_pronto


def reset_modelos():
    """Limpa cache dos modelos para forçar reload"""
    global _classificador, _busca
    _classificador = None
    _busca = None
