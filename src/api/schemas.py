"""
Schemas Pydantic - SharkIA API
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class ProdutoRequest(BaseModel):
    produto: str = Field(..., description="Descrição do produto", example="Monitor LED Dell 24 polegadas")
    top_k: int = Field(10, description="Número de candidatos para busca", ge=1, le=50)


class ConfirmarRequest(BaseModel):
    pesquisa_id: str = Field(..., description="ID da pesquisa retornado no /classificar")
    opcao_id: str = Field(..., description="ID da opção escolhida como correta")


class LoteRequest(BaseModel):
    produtos: List[str] = Field(..., description="Lista de produtos")


class OpcaoNCM(BaseModel):
    id: str = Field(..., description="ID único desta opção")
    ncm: str = Field(..., description="Código NCM (sem pontos)")
    descricao: str = Field(..., description="Descrição do NCM")
    score_match: float = Field(0.0, description="Score de similaridade semântica da IA (0 a 1)")
    score_match_percentual: str = Field("N/A", description="Score de match em porcentagem")
    score_usos: float = Field(0.0, description="Score baseado na proporção de usos (0 a 1)")
    score_usos_percentual: str = Field("N/A", description="Proporção de usos em porcentagem")
    usos: int = Field(0, description="Quantas vezes este NCM foi usado para este produto")
    fonte: str = Field("ia", description="Origem: 'historico', 'historico_exato' ou 'ia'")


class ClassificacaoResponse(BaseModel):
    sucesso: bool
    pesquisa_id: str = Field(..., description="ID da pesquisa (usar para confirmar)")
    produto: str
    opcoes: List[OpcaoNCM] = Field(..., description="3 opções de NCM para escolher")
    metodo: Optional[str] = None
    justificativa: Optional[str] = None
    expira_em: Optional[str] = None
    erro: Optional[str] = None


class ConfirmacaoResponse(BaseModel):
    sucesso: bool
    mensagem: str
    ncm: Optional[str] = None
    descricao: Optional[str] = None


class BuscaRequest(BaseModel):
    query: str = Field(..., description="Texto de busca")
    top_k: int = Field(10, description="Número de resultados", ge=1, le=50)


class ValidacaoRequest(BaseModel):
    registro_id: str = Field(..., description="ID do registro a validar")
    correto: bool = Field(..., description="Se a classificação estava correta")
    ncm_correto: Optional[str] = Field(None, description="NCM correto se o original estava errado")


class DescarteRequest(BaseModel):
    pesquisa_id: str = Field(..., description="ID da pesquisa")
    opcao_id: str = Field(..., description="ID da opção a descartar")
    motivo: Optional[str] = Field("", description="Motivo do descarte (opcional)")


class DescarteResponse(BaseModel):
    sucesso: bool
    mensagem: str
    ncm: Optional[str] = None
    contador: Optional[int] = None


class DeletarClassificacaoRequest(BaseModel):
    produto: str = Field(..., description="Descrição exata do produto")
    ncm: Optional[str] = Field(None, description="NCM específico (se não informado, deleta todos do produto)")
