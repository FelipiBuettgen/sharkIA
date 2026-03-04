"""
Cliente Google Gemini - API gratuita (1.500 req/dia)
Usado como backup do Groq
Com rate limiting integrado
"""
from typing import List, Dict, Optional
from pathlib import Path
import re

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from src.utils.rate_limiter import verificar_limite, aguardar_intervalo, RateLimitExceeded


class GeminiClient:
    """Cliente para API Google Gemini (gratuito)"""
    
    def __init__(self, api_key: str = GEMINI_API_KEY):
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY não configurada!\n"
                "1. Acesse: https://makersuite.google.com/app/apikey\n"
                "2. Crie uma API key\n"
                "3. Adicione no arquivo .env: GEMINI_API_KEY=sua_key"
            )
        
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(GEMINI_MODEL)
    
    def classificar_ncm(
        self, 
        produto: str, 
        candidatos: List[Dict],
        temperatura: float = 0.1
    ) -> Dict:
        """
        Usa Gemini para escolher o NCM correto entre candidatos
        """
        
        lista_candidatos = "\n".join([
            f"- {c['codigo']}: {c['descricao']}"
            for c in candidatos
        ])
        
        prompt = f"""Você é um especialista em classificação fiscal NCM (Nomenclatura Comum do Mercosul).

PRODUTO A CLASSIFICAR:
"{produto}"

CANDIDATOS (escolha o mais adequado):
{lista_candidatos}

REGRAS:
1. Analise a natureza e uso do produto
2. Escolha o NCM mais específico e adequado
3. Se nenhum for adequado, indique o mais próximo

RESPONDA EXATAMENTE NESTE FORMATO JSON (sem markdown):
{{"ncm_codigo": "XXXX.XX.XX", "confianca": "alta/media/baixa", "justificativa": "Explicação breve"}}"""

        try:
            # Rate limiting
            verificar_limite("gemini")
            aguardar_intervalo("gemini")
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperatura,
                    "max_output_tokens": 200
                }
            )
            
            resposta_texto = response.text.strip()
            
            import json
            import re
            
            # Remover markdown se presente
            resposta_texto = re.sub(r'```json\s*', '', resposta_texto)
            resposta_texto = re.sub(r'```\s*', '', resposta_texto)
            
            json_match = re.search(r'\{[^}]+\}', resposta_texto, re.DOTALL)
            if json_match:
                resultado = json.loads(json_match.group())
                resultado['modelo'] = GEMINI_MODEL
                resultado['provider'] = 'gemini'
                return resultado
            else:
                return {
                    "ncm_codigo": candidatos[0]['codigo'] if candidatos else None,
                    "confianca": "baixa",
                    "justificativa": "Falha ao parsear resposta da IA",
                    "resposta_raw": resposta_texto,
                    "modelo": GEMINI_MODEL,
                    "provider": "gemini"
                }
                
        except RateLimitExceeded as e:
            return {
                "ncm_codigo": None,
                "confianca": "erro",
                "justificativa": f"Rate limit atingido: {e.mensagem}",
                "modelo": GEMINI_MODEL,
                "provider": "gemini",
                "rate_limit_exceeded": True
            }
        except Exception as e:
            return {
                "ncm_codigo": None,
                "confianca": "erro",
                "justificativa": f"Erro na API: {str(e)}",
                "modelo": GEMINI_MODEL,
                "provider": "gemini"
            }
    
    def enriquecer_ncm(self, ncm: Dict) -> Dict:
        """Gera palavras-chave e exemplos para um NCM"""
        prompt = f"""NCM: {ncm['codigo']}
Descrição oficial: {ncm['descricao']}

Gere dados para melhorar a busca deste NCM.

RESPONDA APENAS EM JSON (sem markdown):
{{"palavras_chave": ["termo1", "termo2"], "exemplos_produtos": ["produto1", "produto2"], "categoria_comercial": "Categoria"}}"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 300
                }
            )
            
            resposta_texto = response.text.strip()
            resposta_texto = re.sub(r'```json\s*', '', resposta_texto)
            resposta_texto = re.sub(r'```\s*', '', resposta_texto)
            
            import json
            import re
            
            json_match = re.search(r'\{[^}]+\}', resposta_texto, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            pass
        
        return {
            "palavras_chave": [],
            "exemplos_produtos": [],
            "categoria_comercial": ""
        }


if __name__ == "__main__":
    try:
        client = GeminiClient()
        print("✅ Gemini conectado!")
        
        resultado = client.classificar_ncm(
            produto="Smartphone Samsung Galaxy S24",
            candidatos=[
                {"codigo": "8517.12.31", "descricao": "Telefones celulares"},
                {"codigo": "8517.12.39", "descricao": "Outros telefones"},
                {"codigo": "8471.30.19", "descricao": "Máquinas automáticas"},
            ]
        )
        print(f"Resultado: {resultado}")
        
    except ValueError as e:
        print(f"⚠️ {e}")
