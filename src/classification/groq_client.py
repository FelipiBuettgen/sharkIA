"""
Cliente Groq - API gratuita (14.400 req/dia)
Com rate limiting integrado
"""
from typing import List, Dict, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import GROQ_API_KEY, GROQ_MODEL
from src.utils.rate_limiter import verificar_limite, aguardar_intervalo, RateLimitExceeded


class GroqClient:
    """Cliente para API Groq (Llama 3.1 gratuito)"""
    
    def __init__(self, api_key: str = GROQ_API_KEY):
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY não configurada!\n"
                "1. Crie conta em: https://console.groq.com\n"
                "2. Gere uma API key\n"
                "3. Adicione no arquivo .env: GROQ_API_KEY=sua_key"
            )
        
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model = GROQ_MODEL
    
    def classificar_ncm(
        self, 
        produto: str, 
        candidatos: List[Dict],
        temperatura: float = 0.1
    ) -> Dict:
        """
        Usa IA para escolher o NCM correto entre candidatos
        
        Args:
            produto: Descrição do produto (ex: "Monitor LED Dell 24pol")
            candidatos: Lista de NCMs candidatos da busca semântica
            temperatura: Criatividade (0.1 = mais preciso)
            
        Returns:
            Dict com NCM escolhido e justificativa
        """
        
        # Formatar candidatos para o prompt
        lista_candidatos = "\n".join([
            f"- {c['codigo']}: {c['descricao']}"
            for c in candidatos
        ])
        
        prompt = f"""Você é um especialista brasileiro em classificação fiscal NCM (Nomenclatura Comum do Mercosul).

PRODUTO A CLASSIFICAR:
"{produto}"

CANDIDATOS DA BUSCA:
{lista_candidatos}

CONHECIMENTO IMPORTANTE:
- Termos brasileiros de carnes: picanha, maminha, alcatra, contrafilé, fraldinha são CORTES BOVINOS (capítulo 02)
- Carnes desossadas congeladas: 0202.30.00
- Carnes desossadas frescas/refrigeradas: 0201.30.00
- Miudezas: 0206.xx.xx
- Aves (frango, peru): 0207.xx.xx
- Suínos: 0203.xx.xx
- Peixes: 0302-0304

REGRAS:
1. Interprete o produto considerando termos brasileiros/regionais
2. Se o produto é uma CARNE BOVINA (picanha, alcatra, etc.), use obrigatoriamente capítulo 02
3. Se nenhum candidato for adequado, sugira o NCM correto baseado no seu conhecimento
4. Escolha SEMPRE o NCM mais específico para o produto

RESPONDA EXATAMENTE NESTE FORMATO JSON:
{{
    "ncm_codigo": "XXXX.XX.XX",
    "confianca": "alta/media/baixa",
    "justificativa": "Explicação breve"
}}"""

        try:
            # Rate limiting
            verificar_limite("groq")
            aguardar_intervalo("groq")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um classificador fiscal NCM. Responda apenas em JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperatura,
                max_tokens=200
            )
            
            resposta_texto = response.choices[0].message.content.strip()
            
            # Extrair JSON da resposta
            import json
            import re
            
            # Tentar encontrar JSON na resposta
            json_match = re.search(r'\{[^}]+\}', resposta_texto, re.DOTALL)
            if json_match:
                resultado = json.loads(json_match.group())
                resultado['modelo'] = self.model
                resultado['provider'] = 'groq'
                return resultado
            else:
                return {
                    "ncm_codigo": candidatos[0]['codigo'] if candidatos else None,
                    "confianca": "baixa",
                    "justificativa": "Falha ao parsear resposta da IA",
                    "resposta_raw": resposta_texto,
                    "modelo": self.model,
                    "provider": "groq"
                }
                
        except RateLimitExceeded as e:
            return {
                "ncm_codigo": None,
                "confianca": "erro",
                "justificativa": f"Rate limit atingido: {e.mensagem}",
                "modelo": self.model,
                "provider": "groq",
                "rate_limit_exceeded": True
            }
        except Exception as e:
            return {
                "ncm_codigo": None,
                "confianca": "erro",
                "justificativa": f"Erro na API: {str(e)}",
                "modelo": self.model,
                "provider": "groq"
            }
    
    def enriquecer_ncm(self, ncm: Dict) -> Dict:
        """
        Gera palavras-chave e exemplos para um NCM
        Usado para enriquecimento da base
        """
        prompt = f"""NCM: {ncm['codigo']}
Descrição oficial: {ncm['descricao']}

Gere dados para melhorar a busca deste NCM:

RESPONDA EM JSON:
{{
    "palavras_chave": ["palavra1", "palavra2", ...],  // 5-10 termos de busca
    "exemplos_produtos": ["produto1", "produto2", ...],  // 3-5 exemplos reais
    "categoria_comercial": "Categoria > Subcategoria"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um especialista em produtos e classificação NCM. Responda apenas em JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            resposta_texto = response.choices[0].message.content.strip()
            
            import json
            import re
            
            json_match = re.search(r'\{[^}]+\}', resposta_texto, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            pass
        
        # Fallback: retorna vazio
        return {
            "palavras_chave": [],
            "exemplos_produtos": [],
            "categoria_comercial": ""
        }


if __name__ == "__main__":
    # Teste
    try:
        client = GroqClient()
        print("✅ Groq conectado!")
        
        # Teste de classificação
        resultado = client.classificar_ncm(
            produto="Monitor LED Dell 24 polegadas Full HD",
            candidatos=[
                {"codigo": "8528.52.00", "descricao": "Monitores capazes de serem conectados a máquinas"},
                {"codigo": "8528.59.00", "descricao": "Outros monitores"},
                {"codigo": "8471.60.62", "descricao": "Monitores com tubo de raios catódicos"},
            ]
        )
        print(f"Resultado: {resultado}")
        
    except ValueError as e:
        print(f"⚠️ {e}")
