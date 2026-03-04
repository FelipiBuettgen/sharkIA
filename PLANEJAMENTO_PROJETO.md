# 🦈 SharkIA - Planejamento do Projeto NCM

## 📊 Base de Dados Oficial (Siscomex)

### Fonte: `Tabela_NCM_Vigente.json`
| Métrica | Valor |
|---------|-------|
| Data de Atualização | 26/02/2026 |
| Ato Legal | Resolução Gecex nº 812/2025 |
| Total de registros | 15.156 |
| **NCMs classificáveis (8 dígitos)** | **10.515** |
| Capítulos (2 dígitos) | 96 |
| Posições (4 dígitos) | 957 |
| Subposições (6 dígitos) | 1.661 |

### Estrutura de Cada NCM
```json
{
    "Codigo": "8528.52.00",
    "Descricao": "Capazes de serem conectados diretamente a uma máquina...",
    "Data_Inicio": "01/04/2022",
    "Data_Fim": "31/12/9999",
    "Tipo_Ato_Ini": "Res Camex",
    "Numero_Ato_Ini": "272",
    "Ano_Ato_Ini": "2021"
}
```

### Capítulos com Mais NCMs (8 dígitos)
| Capítulo | Descrição | NCMs |
|----------|-----------|------|
| 29 | Produtos químicos orgânicos | 1.643 |
| 84 | Máquinas e equipamentos | 1.121 |
| 85 | Eletrônicos | 645 |
| 28 | Produtos químicos inorgânicos | 420 |
| 30 | Produtos farmacêuticos | 406 |
| 90 | Instrumentos de precisão | 372 |

### ⚠️ Arquivo Excel "Enriquecido" (DESCARTADO)
A tabela `Tabela_NCM_Enriquecida.xlsx` tinha sinônimos gerados por IA com baixa qualidade (ruído, marcas incorretas). **Usaremos apenas o JSON oficial.**

---

## 🎯 Arquitetura Proposta (Sem OLLAMA)

### Opção 1: API de IA Gratuita (RECOMENDADA)

```
┌──────────────────────────────────────────────────────────────┐
│                    FLUXO DE CLASSIFICAÇÃO                     │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────────┐ │
│  │ Usuário │───▶│ Pré-processo │───▶│ Busca Semântica      │ │
│  │ Input   │    │ (Normalizar) │    │ (Filtrar Candidatos) │ │
│  └─────────┘    └──────────────┘    └──────────┬───────────┘ │
│                                                 │             │
│                                                 ▼             │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────────┐ │
│  │ NCM     │◀───│ Validação    │◀───│ API IA Gratuita      │ │
│  │ Final   │    │ (Confiança)  │    │ (Ranking + Decisão)  │ │
│  └─────────┘    └──────────────┘    └──────────────────────┘ │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### APIs de IA Gratuitas Viáveis

| API | Limite Gratuito | Vantagens | Desvantagens |
|-----|-----------------|-----------|--------------|
| **Google Gemini** | 1.500 req/dia (Flash) | Rápido, bom português | Limite diário |
| **Groq** | 14.400 req/dia (Llama3) | Muito rápido, alta quota | Modelos menores |
| **Hugging Face** | Ilimitado (inferência) | Gratuito total | Mais lento |
| **Mistral AI** | 1M tokens/mês (gratuito) | Boa qualidade | Limite mensal |
| **OpenRouter** | Modelos gratuitos | Agregador, opções | Variável |

**RECOMENDAÇÃO**: Usar **Groq + Llama 3.1** como principal (rápido, 14.400 req/dia) e **Google Gemini Flash** como backup.

---

## 📁 Fontes de Dados NCM Gratuitas

### 1. Fontes Oficiais (Download)

| Fonte | URL | Dados |
|-------|-----|-------|
| **Portal Siscomex** | portalunico.siscomex.gov.br | Tabela NCM oficial atualizada |
| **Receita Federal** | receita.economia.gov.br | TIPI (Tabela IPI com alíquotas) |
| **MDIC** | mdic.gov.br | NCM + Dados de comércio exterior |
| **IBGE/CONCLA** | concla.ibge.gov.br | Correlação NCM x CNAE x PRODLIST |

### 2. APIs Gratuitas de Consulta

```python
# API Cosmos (gratuita, sem autenticação)
# Retorna NCMs com descrições, alíquotas IPI, unidade tributável
url = f"https://api.cosmos.bluesoft.com.br/ncms/{codigo_ncm}"

# BrasilAPI (gratuita)  
url = f"https://brasilapi.com.br/api/ncm/v1/{codigo_ncm}"
```

### 3. Bases Complementares

| Base | Descrição | Uso |
|------|-----------|-----|
| **COMEX Stat** | Dados de importação/exportação | Produtos mais comercializados |
| **Notas Fiscais Públicas** | NFe públicas (dados abertos) | Relação produto x NCM real |
| **Catálogos B2B** | Sites como Cosmos, Sintegra | Produtos com NCM validado |

---

## 🔧 Pipeline de Enriquecimento de Dados

### Fase 1: Processar JSON Oficial

```python
# Carregar JSON do Siscomex
with open('Tabela/Tabela_NCM_Vigente.json', 'r') as f:
    data = json.load(f)

# Filtrar apenas NCMs de 8 dígitos (classificáveis)
ncms_8_digitos = [n for n in data['Nomenclaturas'] 
                  if re.match(r'^\d{4}\.\d{2}\.\d{2}$', n['Codigo'])]
# Total: 10.515 NCMs
```

### Fase 2: Enriquecimento via IA Gratuita

Para cada NCM, gerar via Groq/Gemini:
```json
{
    "codigo": "8528.52.00",
    "descricao_oficial": "Monitores capazes de serem conectados...",
    
    // CAMPOS GERADOS POR IA
    "palavras_chave": ["monitor", "tela", "display", "led", "lcd"],
    "exemplos_produtos": ["Monitor Dell 24pol", "Monitor LG IPS"],
    "categoria_comercial": "Informática > Monitores",
    "termos_tecnicos": ["resolução", "taxa atualização", "hdmi"]
}
```

### Fase 2: Geração de Embeddings

```python
# Usar modelo de embeddings gratuito
from sentence_transformers import SentenceTransformer

# Modelo multilíngue gratuito (offline)
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# Criar embedding para cada NCM
texto_ncm = f"{descricao} {sinonimos} {palavras_chave}"
embedding = model.encode(texto_ncm)
```

### Fase 3: Busca e Classificação

```
1. Usuário digita: "Monitor LG 24 polegadas LED"

2. Gerar embedding do input

3. Buscar Top 10 NCMs mais similares (cosine similarity)

4. Enviar candidatos para API de IA:
   "Qual o NCM correto para 'Monitor LG 24 polegadas LED'?
    Candidatos:
    - 8528.52.00: Monitores de vídeo
    - 8528.59.00: Outros monitores
    - 8471.60.62: Monitores LED
    Responda apenas o código NCM."

5. Retornar NCM com confiança
```

---

## 📋 Plano de Implementação

### Etapa 1: Processar JSON Oficial (Prioridade MÁXIMA)

| Tarefa | Tempo | Descrição |
|--------|-------|-----------|
| Parsear JSON Siscomex | 30min | Extrair 10.515 NCMs de 8 dígitos |
| Criar hierarquia | 1h | Mapear Capítulo → Posição → NCM |
| Exportar base limpa | 30min | Gerar SQLite/Parquet processado |

### Etapa 2: Enriquecimento via IA (Prioridade ALTA)

| Tarefa | Tempo | Descrição |
|--------|-------|-----------|
| Configurar API Groq | 30min | Criar conta, obter key gratuita |
| Script de enriquecimento | 2h | Gerar palavras-chave para cada NCM |
| Processar 10.515 NCMs | ~3h | Em batches (respeitando limites) |
| Validar qualidade | 1h | Amostragem manual |

### Etapa 2: Sistema de Embeddings (Prioridade ALTA)

| Tarefa | Tempo | Descrição |
|--------|-------|-----------|
| Instalar sentence-transformers | 30min | Biblioteca de embeddings |
| Gerar embeddings NCM | 2h | Processar 15.156 registros |
| Criar índice de busca | 1h | FAISS ou similar |
| Testar busca semântica | 2h | Validar resultados |

### Etapa 3: Integração com IA (Prioridade MÉDIA)

| Tarefa | Tempo | Descrição |
|--------|-------|-----------|
| Configurar API Groq | 1h | Criar conta, obter key |
| Criar prompts otimizados | 2h | Testar diferentes prompts |
| Implementar fallback Gemini | 1h | Caso Groq falhe |
| Cache de respostas | 1h | Evitar chamadas repetidas |

### Etapa 4: Interface e Validação (Prioridade BAIXA)

| Tarefa | Tempo | Descrição |
|--------|-------|-----------|
| API REST local | 2h | FastAPI ou Flask |
| Interface web simples | 3h | HTML/JS ou Streamlit |
| Sistema de feedback | 2h | Usuário valida respostas |
| Logs e métricas | 1h | Monitorar acurácia |

---

## 💰 Custos

| Item | Custo |
|------|-------|
| APIs de IA | **GRATUITO** |
| Dados NCM | **GRATUITO** |
| Embeddings (local) | **GRATUITO** |
| Hospedagem (local) | **GRATUITO** |
| **TOTAL** | **R$ 0,00** |

---

## 🚀 Próximos Passos Imediatos

1. **Criar conta no Groq** (console.groq.com) - API key gratuita
2. **Processar JSON oficial** - Extrair 10.515 NCMs de 8 dígitos
3. **Instalar dependências**:
   ```bash
   pip install sentence-transformers faiss-cpu groq google-generativeai
   ```
4. **Enriquecer NCMs** via Groq (palavras-chave, exemplos)
5. **Criar embeddings** para busca semântica
6. **Implementar classificador** com API de IA

---

## 📝 Arquivos a Criar

```
sharkIA/
├── Tabela/
│   └── Tabela_NCM_Vigente.json   # ✅ Fonte oficial (já existe)
├── data/
│   ├── ncm_processado.json       # NCMs de 8 dígitos extraídos
│   ├── ncm_enriquecido.json      # Com palavras-chave geradas
│   └── embeddings.npy            # Vetores de embedding
├── src/
│   ├── data/
│   │   ├── parser.py             # Processar JSON oficial
│   │   └── enricher.py           # Enriquecimento via IA
│   ├── search/
│   │   ├── embeddings.py         # Geração de embeddings
│   │   └── semantic_search.py    # Busca vetorial
│   ├── classification/
│   │   ├── groq_client.py        # Cliente Groq
│   │   ├── gemini_client.py      # Cliente Gemini (backup)
│   │   └── classifier.py         # Lógica de classificação
│   └── api/
│       └── main.py               # API FastAPI
├── config/
│   └── settings.py               # Configurações
└── requirements.txt
```

---

## ✅ Decisão Técnica Final

| Aspecto | Escolha | Justificativa |
|---------|---------|---------------|
| **IA Principal** | Groq (Llama 3.1 70B) | 14.400 req/dia grátis, rápido |
| **IA Backup** | Google Gemini Flash | 1.500 req/dia grátis |
| **Embeddings** | sentence-transformers | Offline, gratuito, multilíngue |
| **Busca Vetorial** | FAISS | Rápido, gratuito, local |
| **Base de Dados** | Parquet/SQLite | Leve, sem servidor |
| **API** | FastAPI | Rápido, simples, documentado |

---

*Documento atualizado em: 02/03/2026*
*Fonte de dados: Siscomex - Tabela_NCM_Vigente.json (26/02/2026)*
*Projeto: SharkIA - Classificador NCM Inteligente*
