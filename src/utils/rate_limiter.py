"""
Rate Limiter - Controle de requisições para APIs externas
"""
import time
from typing import Dict, Optional
from functools import wraps
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.data.database import verificar_rate_limit, obter_status_rate_limits


# Limites diários de cada provider (gratuitos)
LIMITES_DIARIOS = {
    "groq": 14400,      # 14.400 req/dia
    "gemini": 1500,     # 1.500 req/dia
    "huggingface": 30000,  # 30.000 req/dia (aproximado)
}

# Intervalo mínimo entre requisições (em segundos) - evita burst
INTERVALO_MINIMO = {
    "groq": 0.1,       # 100ms entre requisições
    "gemini": 0.5,     # 500ms entre requisições
}

# Estado em memória para rate limiting local
_ultimo_request = {}


class RateLimitExceeded(Exception):
    """Exceção quando o rate limit é atingido"""
    def __init__(self, provider: str, reset_em: str, mensagem: str = ""):
        self.provider = provider
        self.reset_em = reset_em
        self.mensagem = mensagem or f"Rate limit atingido para {provider}. Reset em: {reset_em}"
        super().__init__(self.mensagem)


def verificar_limite(provider: str) -> Dict:
    """
    Verifica se pode fazer requisição para o provider
    
    Args:
        provider: Nome do provider (groq, gemini, etc)
        
    Returns:
        Dict com {permitido: bool, restante: int, reset_em: str}
        
    Raises:
        RateLimitExceeded: Se o limite foi atingido
    """
    limite = LIMITES_DIARIOS.get(provider, 1000)
    resultado = verificar_rate_limit(provider, limite)
    
    if not resultado['permitido']:
        raise RateLimitExceeded(
            provider=provider,
            reset_em=resultado['reset_em'],
            mensagem=resultado.get('mensagem', '')
        )
    
    return resultado


def aguardar_intervalo(provider: str):
    """Aguarda intervalo mínimo entre requisições (evita burst)"""
    intervalo = INTERVALO_MINIMO.get(provider, 0.1)
    ultimo = _ultimo_request.get(provider, 0)
    agora = time.time()
    
    tempo_desde_ultimo = agora - ultimo
    if tempo_desde_ultimo < intervalo:
        time.sleep(intervalo - tempo_desde_ultimo)
    
    _ultimo_request[provider] = time.time()


def rate_limited(provider: str):
    """
    Decorator para aplicar rate limiting em funções
    
    Uso:
        @rate_limited("groq")
        def fazer_requisicao():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Verificar limite diário
            verificar_limite(provider)
            
            # Aguardar intervalo mínimo
            aguardar_intervalo(provider)
            
            # Executar função
            return func(*args, **kwargs)
        return wrapper
    return decorator


def status_limites() -> Dict:
    """Retorna status atual de todos os rate limits"""
    status = obter_status_rate_limits()
    
    resultado = {}
    for provider, limite in LIMITES_DIARIOS.items():
        if provider in status:
            resultado[provider] = {
                "limite_diario": limite,
                "usado": status[provider].get('contador', 0),
                "restante": limite - status[provider].get('contador', 0),
                "ultima_requisicao": status[provider].get('ultima_requisicao'),
                "reset_em": status[provider].get('reset_diario')
            }
        else:
            resultado[provider] = {
                "limite_diario": limite,
                "usado": 0,
                "restante": limite,
                "ultima_requisicao": None,
                "reset_em": None
            }
    
    return resultado


def pode_usar_provider(provider: str) -> bool:
    """Verifica rapidamente se um provider está disponível"""
    try:
        limite = LIMITES_DIARIOS.get(provider, 1000)
        resultado = verificar_rate_limit(provider, limite)
        # Não conta a verificação como uso (rollback implícito)
        return resultado['permitido']
    except Exception:
        return False


def escolher_provider_disponivel(preferencia: list = None) -> Optional[str]:
    """
    Escolhe o primeiro provider disponível da lista de preferência
    
    Args:
        preferencia: Lista de providers em ordem de preferência
                    Default: ["groq", "gemini"]
    
    Returns:
        Nome do provider disponível ou None
    """
    if preferencia is None:
        preferencia = ["groq", "gemini"]
    
    for provider in preferencia:
        if pode_usar_provider(provider):
            return provider
    
    return None


if __name__ == "__main__":
    print("📊 Status dos Rate Limits:\n")
    status = status_limites()
    
    for provider, info in status.items():
        print(f"🔹 {provider.upper()}")
        print(f"   Limite: {info['limite_diario']} req/dia")
        print(f"   Usado: {info['usado']}")
        print(f"   Restante: {info['restante']}")
        print()
