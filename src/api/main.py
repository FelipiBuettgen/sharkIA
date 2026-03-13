"""
API REST - SharkIA Classificador NCM
Ponto de entrada: registra routers e configura startup.
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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

print("📦 Importando módulo de banco de dados...")

# Importar banco (auto-inicializa ao importar)
import src.data.database  # noqa: F401

print("✅ Banco de dados importado!")

# Importar dependências compartilhadas
from src.api.deps import get_busca, get_classificador, set_sistema_pronto, is_sistema_pronto

# Importar routers
from src.api.routes.classificacao import router as classificacao_router
from src.api.routes.confirmar import router as confirmar_router
from src.api.routes.busca import router as busca_router
from src.api.routes.aprendizado import router as aprendizado_router
from src.api.routes.descartes import router as descartes_router
from src.api.routes.usuario import router as usuario_router
from src.api.routes.admin import router as admin_router

app = FastAPI(
    title="🦈 SharkIA - Classificador NCM",
    description="API inteligente para classificação de produtos em códigos NCM",
    version="2.1.0"
)

print("✅ FastAPI app criado!")

# Middleware para bypass do aviso do ngrok no plano gratuito
class NgrokBypassMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokBypassMiddleware)

# CORS para acesso do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ngrok-skip-browser-warning"],
)


# ==================== Registrar Routers ====================

app.include_router(classificacao_router)
app.include_router(confirmar_router)
app.include_router(busca_router)
app.include_router(aprendizado_router)
app.include_router(descartes_router)
app.include_router(usuario_router)
app.include_router(admin_router)


# ==================== Startup ====================

@app.on_event("startup")
async def startup_event():
    """Pré-carrega modelos em background para não bloquear o healthcheck."""
    import asyncio
    print("\n🚀 API iniciando...")

    try:
        asyncio.create_task(_carregar_modelos_background())
        print("✅ API pronta - modelos carregando em background...\n")
    except Exception as e:
        print(f"⚠️ Erro ao criar task de carregamento: {e}")
        print("✅ API pronta - modelos serão carregados sob demanda\n")


async def _carregar_modelos_background():
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _precarregar_sistemas)
        set_sistema_pronto(True)
        print("✅ Todos os modelos carregados em background!")
    except Exception as e:
        print(f"⚠️ Erro no carregamento de modelos: {e}")


def _precarregar_sistemas():
    try:
        print("⏳ Carregando busca semântica...")
        _ = get_busca()
        print("✅ Busca semântica carregada")

        print("⏳ Carregando classificador...")
        _ = get_classificador()
        print("✅ Classificador carregado")

        print("✅ Todos os sistemas pré-carregados!")
    except Exception as e:
        print(f"⚠️ Erro no pré-carregamento: {e}")


# ==================== Endpoints públicos (sem token) ====================

@app.get("/")
async def root():
    """Endpoint raiz"""
    return {    
        "titulo": "SharkIA - Classificador NCM",
        "versao": "2.1.0",
        "autenticacao": "Header X-User-Token obrigatório em todas as rotas (exceto / e /health)",
        "ngrok": "Adicione o header 'ngrok-skip-browser-warning: true' em TODOS os requests para evitar a página de aviso do ngrok gratuito",
        "fluxo": "1. POST /classificar -> 2. POST /confirmar",
        "endpoints": {
            "classificar": "POST /classificar - Retorna opções de NCM",
            "confirmar": "POST /confirmar - Confirma a opção correta e salva",
            "buscar": "POST /buscar - Busca semântica (sem salvar)",
            "pendentes": "GET /pendentes - Lista pesquisas não confirmadas",
            "descartar": "POST /descartar - Descarta uma opção de NCM",
            "usuario_classificacoes": "GET /usuario/classificacoes - Classificações acatadas do usuário",
            "usuario_descartes": "GET /usuario/descartes - Descartes do usuário",
            "health": "GET /health",
            "status": "GET /status"
        }
    }


@app.get("/health")
async def health():
    """Verifica saúde da API"""
    return {
        "status": "ok",
        "servico": "sharkia",
        "versao": "2.1.0",
        "modelos_carregados": is_sistema_pronto()
    }


@app.get("/status")
async def status():
    """Retorna status completo do sistema incluindo rate limits"""
    try:
        from src.utils.rate_limiter import status_limites
        from src.data.learning import estatisticas_historico

        return {
            "servico": "sharkia",
            "versao": "2.1.0",
            "rate_limits": status_limites(),
            "historico": estatisticas_historico()
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
