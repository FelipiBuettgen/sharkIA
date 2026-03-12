"""
Banco de Dados SQLite - SharkIA
Substitui o armazenamento em JSON para melhor escalabilidade
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager
import threading

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import DATA_DIR


# Caminho do banco de dados
DATABASE_PATH = DATA_DIR / "sharkia.db"

# Lock para thread safety
_db_lock = threading.Lock()


@contextmanager
def get_connection():
    """Context manager para conexão com o banco"""
    conn = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_banco():
    """Cria as tabelas se não existirem"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabela de histórico de classificações
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classificacoes (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                produto TEXT NOT NULL,
                ncm_codigo TEXT NOT NULL,
                ncm_descricao TEXT,
                confianca TEXT,
                metodo TEXT,
                justificativa TEXT,
                validado_usuario INTEGER DEFAULT 0,
                classificacao_correta INTEGER DEFAULT 1,
                ncm_corrigido TEXT,
                usado_treinamento INTEGER DEFAULT 0,
                score_match REAL DEFAULT 0.0,
                usos INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Adicionar coluna score_match se não existir (migração)
        try:
            cursor.execute("ALTER TABLE classificacoes ADD COLUMN score_match REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass  # Coluna já existe
        
        # Adicionar coluna usos se não existir (migração)
        try:
            cursor.execute("ALTER TABLE classificacoes ADD COLUMN usos INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # Coluna já existe
        
        # Índice único para produto+ncm (evitar duplicatas) - pode falhar se houver duplicatas
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_classificacoes_produto_ncm 
                ON classificacoes(LOWER(TRIM(produto)), ncm_codigo)
            """)
        except sqlite3.IntegrityError:
            # Duplicatas existentes - precisa consolidar primeiro
            print("⚠️ Existem duplicatas no banco. Execute consolidar_classificacoes_duplicadas() primeiro.")
        
        # Índices para busca rápida
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_classificacoes_produto 
            ON classificacoes(produto)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_classificacoes_ncm 
            ON classificacoes(ncm_codigo)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_classificacoes_validado 
            ON classificacoes(validado_usuario)
        """)
        
        # Tabela de rate limiting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                provider TEXT PRIMARY KEY,
                contador INTEGER DEFAULT 0,
                ultima_requisicao TEXT,
                reset_diario TEXT
            )
        """)
        
        # Tabela de estatísticas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estatisticas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                total_classificacoes INTEGER DEFAULT 0,
                classificacoes_ia INTEGER DEFAULT 0,
                classificacoes_cache INTEGER DEFAULT 0,
                erros INTEGER DEFAULT 0
            )
        """)
        
        # Tabela de pesquisas pendentes (aguardando confirmação do usuário)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pesquisas_pendentes (
                pesquisa_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                produto TEXT NOT NULL,
                opcao1_id TEXT NOT NULL,
                opcao1_ncm TEXT NOT NULL,
                opcao1_descricao TEXT,
                opcao1_score REAL,
                opcao1_score_match REAL DEFAULT 0.0,
                opcao2_id TEXT NOT NULL,
                opcao2_ncm TEXT NOT NULL,
                opcao2_descricao TEXT,
                opcao2_score REAL,
                opcao2_score_match REAL DEFAULT 0.0,
                opcao3_id TEXT NOT NULL,
                opcao3_ncm TEXT NOT NULL,
                opcao3_descricao TEXT,
                opcao3_score REAL,
                opcao3_score_match REAL DEFAULT 0.0,
                metodo TEXT,
                justificativa TEXT,
                confirmado INTEGER DEFAULT 0,
                expira_em TEXT
            )
        """)
        
        # Adicionar colunas score_match às pesquisas_pendentes (migração)
        for col in ['opcao1_score_match', 'opcao2_score_match', 'opcao3_score_match']:
            try:
                cursor.execute(f"ALTER TABLE pesquisas_pendentes ADD COLUMN {col} REAL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass  # Coluna já existe
        
        # Índice para limpeza de expirados
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pesquisas_expira 
            ON pesquisas_pendentes(expira_em)
        """)
        
        # Tabela de NCMs descartados (feedback negativo)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS descartes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                produto TEXT NOT NULL,
                ncm_codigo TEXT NOT NULL,
                motivo TEXT,
                contador INTEGER DEFAULT 1
            )
        """)
        
        # Índices para busca rápida de descartes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_descartes_produto 
            ON descartes(produto)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_descartes_ncm 
            ON descartes(ncm_codigo)
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_descartes_produto_ncm 
            ON descartes(LOWER(TRIM(produto)), ncm_codigo)
        """)
        
        # Tabela de cache de respostas da IA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_ia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_hash TEXT UNIQUE NOT NULL,
                produto TEXT NOT NULL,
                ncm_codigo TEXT NOT NULL,
                ncm_descricao TEXT,
                confianca TEXT,
                justificativa TEXT,
                provider TEXT,
                modelo TEXT,
                timestamp TEXT NOT NULL,
                acessos INTEGER DEFAULT 1
            )
        """)
        
        # Índice para busca rápida no cache
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_ia_hash 
            ON cache_ia(produto_hash)
        """)
        
        # Tabela de NCMs (dados base da tabela oficial)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ncms (
                codigo TEXT PRIMARY KEY,
                codigo_formatado TEXT NOT NULL,
                descricao TEXT NOT NULL,
                capitulo TEXT,
                posicao TEXT,
                data_inicio TEXT,
                data_fim TEXT,
                ativo INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices para NCMs
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ncms_capitulo 
            ON ncms(capitulo)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ncms_descricao 
            ON ncms(descricao)
        """)
        
        # Tabela de termos aprendidos por NCM
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS termos_ncm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ncm_codigo TEXT NOT NULL,
                termo TEXT NOT NULL,
                frequencia INTEGER DEFAULT 1,
                origem TEXT DEFAULT 'classificacao',
                validado INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ncm_codigo) REFERENCES ncms(codigo)
            )
        """)
        
        # Índice único para evitar duplicatas
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_termos_ncm_unico 
            ON termos_ncm(ncm_codigo, LOWER(TRIM(termo)))
        """)
        
        # Índice para busca rápida
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_termos_ncm_codigo 
            ON termos_ncm(ncm_codigo)
        """)
        
        conn.commit()
        print(f"✅ Banco de dados inicializado: {DATABASE_PATH}")
    
    # Verificar se a tabela ncms está vazia e popular se necessário
    _popular_ncms_se_vazio()


def _popular_ncms_se_vazio():
    """Popula a tabela ncms a partir do JSON se estiver vazia"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ncms")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"   ℹ️ Tabela ncms já possui {count} registros")
            return
        
        print("📂 Populando tabela ncms a partir do JSON...")
        
        # Tentar carregar do ncm_processado.json
        ncm_json_path = DATA_DIR / "ncm_processado.json"
        
        if not ncm_json_path.exists():
            print(f"   ⚠️ Arquivo {ncm_json_path} não encontrado!")
            return
        
        try:
            import json
            with open(ncm_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            ncms = data.get('ncms', [])
            print(f"   📦 Carregando {len(ncms)} NCMs do JSON...")
            
            for ncm in ncms:
                codigo = ncm.get('codigo', '').replace('.', '')
                codigo_formatado = ncm.get('codigo', '')
                descricao = ncm.get('descricao', '')
                capitulo = codigo[:2] if len(codigo) >= 2 else ''
                posicao = codigo[:4] if len(codigo) >= 4 else ''
                data_inicio = ncm.get('data_inicio', '')
                data_fim = ncm.get('data_fim', '')
                
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO ncms 
                        (codigo, codigo_formatado, descricao, capitulo, posicao, data_inicio, data_fim)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (codigo, codigo_formatado, descricao, capitulo, posicao, data_inicio, data_fim))
                except Exception as e:
                    print(f"   ⚠️ Erro ao inserir NCM {codigo}: {e}")
            
            conn.commit()
            
            # Verificar quantos foram inseridos
            cursor.execute("SELECT COUNT(*) FROM ncms")
            total = cursor.fetchone()[0]
            print(f"   ✅ {total} NCMs carregados com sucesso!")
            
        except Exception as e:
            print(f"   ❌ Erro ao carregar NCMs: {e}")



# ==================== CRUD Classificações ====================

def inserir_classificacao(
    produto: str,
    ncm_codigo: str,
    ncm_descricao: str,
    confianca: str,
    metodo: str,
    justificativa: str = "",
    validado_usuario: bool = False,
    score_match: float = 0.0
) -> Dict:
    """
    Insere ou atualiza uma classificação no banco.
    Se já existe produto+NCM idêntico, incrementa usos e mantém a melhor justificativa (da IA).
    """
    timestamp = datetime.now().isoformat()
    ncm_normalizado = normalizar_ncm(ncm_codigo)
    produto_normalizado = produto.strip()
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar se já existe registro com mesmo produto+NCM
            cursor.execute("""
                SELECT id, usos, justificativa, metodo, score_match 
                FROM classificacoes 
                WHERE LOWER(TRIM(produto)) = LOWER(TRIM(?)) AND ncm_codigo = ?
            """, (produto_normalizado, ncm_normalizado))
            
            existente = cursor.fetchone()
            
            if existente:
                # Atualizar registro existente
                registro_id = existente['id']
                usos_atual = (existente['usos'] or 1) + 1
                
                # Manter a justificativa da IA (mais descritiva) se a atual for genérica
                justificativa_existente = existente['justificativa'] or ''
                metodo_existente = existente['metodo'] or ''
                
                # Priorizar justificativa de IA sobre histórico
                if metodo.startswith('ia_') and len(justificativa) > len(justificativa_existente):
                    nova_justificativa = justificativa
                elif metodo_existente.startswith('ia_'):
                    nova_justificativa = justificativa_existente
                else:
                    nova_justificativa = justificativa if len(justificativa) > len(justificativa_existente) else justificativa_existente
                
                # Usar o maior score_match
                score_existente = existente['score_match'] or 0.0
                novo_score = max(score_match, score_existente)
                
                cursor.execute("""
                    UPDATE classificacoes 
                    SET timestamp = ?,
                        usos = ?,
                        justificativa = ?,
                        score_match = ?,
                        validado_usuario = MAX(validado_usuario, ?),
                        confianca = CASE WHEN ? = 'alta' THEN 'alta' ELSE confianca END
                    WHERE id = ?
                """, (
                    timestamp, 
                    usos_atual, 
                    nova_justificativa, 
                    novo_score,
                    int(validado_usuario),
                    confianca,
                    registro_id
                ))
                
                return {
                    "id": registro_id,
                    "timestamp": timestamp,
                    "produto": produto_normalizado,
                    "ncm_codigo": ncm_normalizado,
                    "ncm_descricao": ncm_descricao,
                    "confianca": confianca,
                    "metodo": metodo,
                    "justificativa": nova_justificativa,
                    "validado_usuario": validado_usuario,
                    "score_match": novo_score,
                    "usos": usos_atual,
                    "atualizado": True
                }
            else:
                # Inserir novo registro
                registro_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
                
                cursor.execute("""
                    INSERT INTO classificacoes 
                    (id, timestamp, produto, ncm_codigo, ncm_descricao, confianca, metodo, justificativa, validado_usuario, score_match, usos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (registro_id, timestamp, produto_normalizado, ncm_normalizado, ncm_descricao, confianca, metodo, justificativa, int(validado_usuario), score_match))
    
    return {
        "id": registro_id,
        "timestamp": timestamp,
        "produto": produto_normalizado,
        "ncm_codigo": ncm_normalizado,
        "ncm_descricao": ncm_descricao,
        "confianca": confianca,
        "metodo": metodo,
        "justificativa": justificativa,
        "validado_usuario": validado_usuario,
        "score_match": score_match,
        "usos": 1,
        "usado_treinamento": False
    }


def buscar_classificacoes(
    produto: Optional[str] = None,
    ncm_codigo: Optional[str] = None,
    validado_apenas: bool = False,
    limite: int = 100
) -> List[Dict]:
    """Busca classificações com filtros"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM classificacoes WHERE 1=1"
        params = []
        
        if produto:
            query += " AND LOWER(produto) LIKE ?"
            params.append(f"%{produto.lower()}%")
        
        if ncm_codigo:
            query += " AND ncm_codigo = ?"
            params.append(ncm_codigo)
        
        if validado_apenas:
            query += " AND validado_usuario = 1"
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limite)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]


def buscar_classificacao_exata(produto: str) -> Optional[Dict]:
    """Busca classificação exata por produto (para cache)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM classificacoes 
            WHERE LOWER(produto) = LOWER(?)
            AND (confianca = 'alta' OR validado_usuario = 1)
            ORDER BY validado_usuario DESC, timestamp DESC
            LIMIT 1
        """, (produto,))
        row = cursor.fetchone()
        return dict(row) if row else None


def buscar_ncms_por_historico(produto: str, limite: int = 10) -> List[Dict]:
    """
    Busca NCMs mais usados para produtos similares
    
    Retorna lista de NCMs ordenada por quantidade de usos,
    incluindo a contagem de vezes que foi classificado.
    
    Args:
        produto: Descrição do produto (busca parcial)
        limite: Máximo de NCMs a retornar
    
    Returns:
        Lista de dicts com {ncm, descricao, usos, score_percentual}
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Normalizar produto para busca
        produto_lower = produto.lower().strip()
        
        # Buscar NCMs agrupados por código, contando usos
        # Prioriza: validado_usuario > alta confiança > outros
        cursor.execute("""
            SELECT 
                ncm_codigo as ncm,
                ncm_descricao as descricao,
                SUM(COALESCE(usos, 1)) as usos,
                SUM(CASE WHEN validado_usuario = 1 THEN 1 ELSE 0 END) as validados,
                MAX(timestamp) as ultimo_uso,
                MAX(COALESCE(score_match, 0.0)) as score_match_salvo
            FROM classificacoes
            WHERE LOWER(produto) LIKE ?
            GROUP BY ncm_codigo
            ORDER BY 
                validados DESC,
                usos DESC,
                ultimo_uso DESC
            LIMIT ?
        """, (f"%{produto_lower}%", limite))
        
        rows = cursor.fetchall()
        
        resultados = []
        for row in rows:
            usos = row['usos']
            validados = row['validados']
            score_match_salvo = row['score_match_salvo'] or 0.0
            
            # Calcular score baseado em usos (mais usos = score maior)
            # Normalizado para 0-1, com bonus para validados
            score_base = min(usos / 10, 1.0)  # Máximo de 100% após 10 usos
            score_bonus = 0.1 if validados > 0 else 0
            score = min(score_base + score_bonus, 1.0)
            
            resultados.append({
                "ncm": normalizar_ncm(row['ncm']),
                "descricao": row['descricao'] or "",
                "usos": usos,
                "validados": validados,
                "score": score,
                "score_percentual": f"{score * 100:.1f}%",
                "score_match": score_match_salvo,
                "score_match_percentual": f"{score_match_salvo * 100:.1f}%" if score_match_salvo > 0 else "N/A",
                "fonte": "historico"
            })
        
        return resultados


def buscar_ncms_por_produto_exato(produto: str, limite: int = 10) -> List[Dict]:
    """
    Busca NCMs para produto EXATAMENTE igual (case insensitive)
    Mais preciso que busca parcial
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                ncm_codigo as ncm,
                ncm_descricao as descricao,
                SUM(COALESCE(usos, 1)) as usos,
                SUM(CASE WHEN validado_usuario = 1 THEN 1 ELSE 0 END) as validados,
                MAX(COALESCE(score_match, 0.0)) as score_match_salvo
            FROM classificacoes
            WHERE LOWER(TRIM(produto)) = LOWER(TRIM(?))
            GROUP BY ncm_codigo
            ORDER BY validados DESC, usos DESC
            LIMIT ?
        """, (produto, limite))
        
        rows = cursor.fetchall()
        
        resultados = []
        for row in rows:
            usos = row['usos']
            validados = row['validados']
            score = min((usos / 5) + (0.2 if validados > 0 else 0), 1.0)
            score_match_salvo = row['score_match_salvo'] or 0.0
            
            resultados.append({
                "ncm": normalizar_ncm(row['ncm']),
                "descricao": row['descricao'] or "",
                "usos": usos,
                "validados": validados,
                "score": score,
                "score_percentual": f"{score * 100:.1f}%",
                "score_match": score_match_salvo,
                "score_match_percentual": f"{score_match_salvo * 100:.1f}%" if score_match_salvo > 0 else "N/A",
                "fonte": "historico_exato"
            })
        
        return resultados


def validar_classificacao(registro_id: str, correto: bool, ncm_correto: str = None):
    """Valida ou corrige uma classificação"""
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            if correto:
                cursor.execute("""
                    UPDATE classificacoes 
                    SET validado_usuario = 1, classificacao_correta = 1
                    WHERE id = ?
                """, (registro_id,))
            else:
                cursor.execute("""
                    UPDATE classificacoes 
                    SET validado_usuario = 1, classificacao_correta = 0, ncm_corrigido = ?
                    WHERE id = ?
                """, (ncm_correto, registro_id))


def deletar_classificacao(registro_id: str) -> bool:
    """
    Deleta uma classificação pelo ID
    
    Args:
        registro_id: ID da classificação a deletar
    
    Returns:
        True se deletou, False se não encontrou
    """
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM classificacoes WHERE id = ?", (registro_id,))
            return cursor.rowcount > 0


def deletar_classificacoes_por_produto(produto: str, ncm_codigo: str = None) -> int:
    """
    Deleta classificações de um produto específico
    
    Args:
        produto: Descrição exata do produto
        ncm_codigo: NCM específico (opcional, se não informado deleta todos do produto)
    
    Returns:
        Quantidade de registros deletados
    """
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            if ncm_codigo:
                cursor.execute(
                    "DELETE FROM classificacoes WHERE LOWER(TRIM(produto)) = LOWER(TRIM(?)) AND ncm_codigo = ?",
                    (produto, normalizar_ncm(ncm_codigo))
                )
            else:
                cursor.execute(
                    "DELETE FROM classificacoes WHERE LOWER(TRIM(produto)) = LOWER(TRIM(?))",
                    (produto,)
                )
            
            return cursor.rowcount


def obter_todas_classificacoes() -> List[Dict]:
    """Retorna todas as classificações (para migração/export)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM classificacoes ORDER BY timestamp DESC")
        return [dict(row) for row in cursor.fetchall()]


def contar_classificacoes() -> int:
    """Conta total de classificações"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM classificacoes")
        return cursor.fetchone()[0]


def estatisticas_banco() -> Dict:
    """Retorna estatísticas do banco"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM classificacoes")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM classificacoes WHERE validado_usuario = 1")
        validados = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM classificacoes WHERE confianca = 'alta'")
        alta_confianca = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT metodo, COUNT(*) as qtd 
            FROM classificacoes 
            GROUP BY metodo
        """)
        por_metodo = {row['metodo']: row['qtd'] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT ncm_codigo, COUNT(*) as qtd 
            FROM classificacoes 
            GROUP BY ncm_codigo 
            ORDER BY qtd DESC 
            LIMIT 10
        """)
        top_ncms = [(row['ncm_codigo'], row['qtd']) for row in cursor.fetchall()]
        
        return {
            "total": total,
            "validados": validados,
            "alta_confianca": alta_confianca,
            "por_metodo": por_metodo,
            "top_ncms": top_ncms
        }


# ==================== Rate Limiting ====================

def verificar_rate_limit(provider: str, limite_diario: int) -> Dict:
    """
    Verifica e atualiza rate limit para um provider
    
    Returns:
        Dict com {permitido: bool, restante: int, reset_em: str}
    """
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar estado atual
            cursor.execute(
                "SELECT * FROM rate_limits WHERE provider = ?",
                (provider,)
            )
            row = cursor.fetchone()
            
            if row is None:
                # Primeira requisição
                cursor.execute("""
                    INSERT INTO rate_limits (provider, contador, ultima_requisicao, reset_diario)
                    VALUES (?, 1, ?, ?)
                """, (provider, datetime.now().isoformat(), hoje))
                return {
                    "permitido": True,
                    "restante": limite_diario - 1,
                    "reset_em": hoje
                }
            
            # Verificar se precisa resetar (novo dia)
            if row['reset_diario'] != hoje:
                cursor.execute("""
                    UPDATE rate_limits 
                    SET contador = 1, ultima_requisicao = ?, reset_diario = ?
                    WHERE provider = ?
                """, (datetime.now().isoformat(), hoje, provider))
                return {
                    "permitido": True,
                    "restante": limite_diario - 1,
                    "reset_em": hoje
                }
            
            # Verificar limite
            contador_atual = row['contador']
            if contador_atual >= limite_diario:
                return {
                    "permitido": False,
                    "restante": 0,
                    "reset_em": hoje,
                    "mensagem": f"Limite diário de {limite_diario} requisições atingido para {provider}"
                }
            
            # Incrementar contador
            cursor.execute("""
                UPDATE rate_limits 
                SET contador = contador + 1, ultima_requisicao = ?
                WHERE provider = ?
            """, (datetime.now().isoformat(), provider))
            
            return {
                "permitido": True,
                "restante": limite_diario - contador_atual - 1,
                "reset_em": hoje
            }


def obter_status_rate_limits() -> Dict:
    """Retorna status de todos os rate limits"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rate_limits")
        rows = cursor.fetchall()
        return {row['provider']: dict(row) for row in rows}


def resetar_rate_limit(provider: str):
    """Reseta manualmente o rate limit de um provider"""
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM rate_limits WHERE provider = ?",
                (provider,)
            )


# ==================== Utilitários NCM ====================

def normalizar_ncm(ncm: str) -> str:
    """Remove pontos do NCM: 0201.30.00 -> 02013000"""
    return ncm.replace('.', '').replace('-', '').strip()


def formatar_ncm(ncm: str) -> str:
    """Adiciona pontos ao NCM: 02013000 -> 0201.30.00"""
    ncm = normalizar_ncm(ncm)
    if len(ncm) == 8:
        return f"{ncm[:4]}.{ncm[4:6]}.{ncm[6:8]}"
    return ncm


# ==================== Pesquisas Pendentes ====================

def criar_pesquisa_pendente(
    produto: str,
    opcoes: list,  # Lista de dicts com {ncm, descricao, score, usos, fonte}
    metodo: str = "",
    justificativa: str = "",
    expira_horas: int = 24
) -> Dict:
    """
    Cria uma pesquisa pendente com opções de NCM
    
    Returns:
        Dict com pesquisa_id e as opções com seus IDs
    """
    import uuid
    from datetime import timedelta
    
    pesquisa_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()
    expira_em = (datetime.now() + timedelta(hours=expira_horas)).isoformat()
    
    # Gerar IDs únicos para cada opção
    opcao1_id = str(uuid.uuid4())[:8]
    opcao2_id = str(uuid.uuid4())[:8]
    opcao3_id = str(uuid.uuid4())[:8]
    
    # Garantir que temos pelo menos 3 opções para o banco (estrutura fixa)
    while len(opcoes) < 3:
        opcoes.append({"ncm": "", "descricao": "N/A", "score": 0.0, "usos": 0, "fonte": "vazio"})
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pesquisas_pendentes 
                (pesquisa_id, timestamp, produto,
                 opcao1_id, opcao1_ncm, opcao1_descricao, opcao1_score, opcao1_score_match,
                 opcao2_id, opcao2_ncm, opcao2_descricao, opcao2_score, opcao2_score_match,
                 opcao3_id, opcao3_ncm, opcao3_descricao, opcao3_score, opcao3_score_match,
                 metodo, justificativa, expira_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pesquisa_id, timestamp, produto,
                opcao1_id, normalizar_ncm(opcoes[0].get('ncm', '')), opcoes[0].get('descricao', ''), opcoes[0].get('score', 0.0), opcoes[0].get('score_match', 0.0),
                opcao2_id, normalizar_ncm(opcoes[1].get('ncm', '')), opcoes[1].get('descricao', ''), opcoes[1].get('score', 0.0), opcoes[1].get('score_match', 0.0),
                opcao3_id, normalizar_ncm(opcoes[2].get('ncm', '')), opcoes[2].get('descricao', ''), opcoes[2].get('score', 0.0), opcoes[2].get('score_match', 0.0),
                metodo, justificativa, expira_em
            ))
    
    # Gerar IDs para todas as opções (não apenas 3)
    ids_opcoes = [opcao1_id, opcao2_id, opcao3_id]
    for _ in range(3, len(opcoes)):
        ids_opcoes.append(str(uuid.uuid4())[:8])
    
    # Montar resposta com apenas opções válidas (filtrar vazios)
    opcoes_resposta = []
    for i, opcao in enumerate(opcoes):
        # Pular opções vazias (sem NCM)
        ncm_normalizado = normalizar_ncm(opcao.get('ncm', ''))
        if not ncm_normalizado or opcao.get('fonte') == 'vazio':
            continue
        
        # Usar campos de score
        score_match = opcao.get('score_match', 0.0)
        score_match_percentual = opcao.get('score_match_percentual', f"{score_match * 100:.1f}%" if score_match > 0 else "N/A")
        score_usos = opcao.get('score_usos', 0.0)
        score_usos_percentual = opcao.get('score_usos_percentual', f"{score_usos * 100:.1f}%" if score_usos > 0 else "N/A")
            
        opcoes_resposta.append({
            "id": ids_opcoes[i] if i < len(ids_opcoes) else str(uuid.uuid4())[:8],
            "ncm": ncm_normalizado,
            "descricao": opcao.get('descricao', ''),
            "score_match": score_match,
            "score_match_percentual": score_match_percentual,
            "score_usos": score_usos,
            "score_usos_percentual": score_usos_percentual,
            "usos": opcao.get('usos', 0),
            "fonte": opcao.get('fonte', 'ia')
        })
    
    return {
        "pesquisa_id": pesquisa_id,
        "produto": produto,
        "opcoes": opcoes_resposta,
        "metodo": metodo,
        "justificativa": justificativa,
        "expira_em": expira_em
    }


def buscar_pesquisa_pendente(pesquisa_id: str) -> Optional[Dict]:
    """Busca uma pesquisa pendente pelo ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM pesquisas_pendentes WHERE pesquisa_id = ? AND confirmado = 0",
            (pesquisa_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def confirmar_pesquisa(pesquisa_id: str, opcao_id: str) -> Optional[Dict]:
    """
    Confirma qual opção da pesquisa é a correta
    Move para classificações e marca como confirmada
    
    Args:
        pesquisa_id: ID da pesquisa
        opcao_id: ID da opção escolhida (1, 2 ou 3)
    
    Returns:
        Dict com a classificação salva ou None se não encontrada
    """
    pesquisa = buscar_pesquisa_pendente(pesquisa_id)
    if not pesquisa:
        return None
    
    # Identificar qual opção foi escolhida
    ncm_escolhido = None
    descricao_escolhida = None
    score_escolhido = None
    score_match_escolhido = 0.0
    
    if opcao_id == pesquisa['opcao1_id']:
        ncm_escolhido = pesquisa['opcao1_ncm']
        descricao_escolhida = pesquisa['opcao1_descricao']
        score_escolhido = pesquisa['opcao1_score']
        score_match_escolhido = pesquisa.get('opcao1_score_match') or 0.0
    elif opcao_id == pesquisa['opcao2_id']:
        ncm_escolhido = pesquisa['opcao2_ncm']
        descricao_escolhida = pesquisa['opcao2_descricao']
        score_escolhido = pesquisa['opcao2_score']
        score_match_escolhido = pesquisa.get('opcao2_score_match') or 0.0
    elif opcao_id == pesquisa['opcao3_id']:
        ncm_escolhido = pesquisa['opcao3_ncm']
        descricao_escolhida = pesquisa['opcao3_descricao']
        score_escolhido = pesquisa['opcao3_score']
        score_match_escolhido = pesquisa.get('opcao3_score_match') or 0.0
    else:
        return None  # ID de opção inválido
    
    # Marcar pesquisa como confirmada
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pesquisas_pendentes SET confirmado = 1 WHERE pesquisa_id = ?",
                (pesquisa_id,)
            )
    
    # Inserir na tabela de classificações
    resultado = inserir_classificacao(
        produto=pesquisa['produto'],
        ncm_codigo=ncm_escolhido,  # Já está normalizado
        ncm_descricao=descricao_escolhida,
        confianca="alta",  # Usuário confirmou
        metodo=pesquisa.get('metodo', 'confirmado_usuario'),
        justificativa=pesquisa.get('justificativa', ''),
        score_match=score_match_escolhido,
        validado_usuario=True
    )
    
    return resultado


def limpar_pesquisas_expiradas():
    """Remove pesquisas pendentes que expiraram"""
    agora = datetime.now().isoformat()
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pesquisas_pendentes WHERE expira_em < ? AND confirmado = 0",
                (agora,)
            )
            deletados = cursor.rowcount
    return deletados


def listar_pesquisas_pendentes(limite: int = 50) -> List[Dict]:
    """Lista pesquisas pendentes não expiradas"""
    agora = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM pesquisas_pendentes 
            WHERE confirmado = 0 AND expira_em > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (agora, limite))
        return [dict(row) for row in cursor.fetchall()]


# ==================== Migração JSON -> SQLite ====================

def consolidar_classificacoes_duplicadas() -> Dict:
    """
    Consolida classificações duplicadas (mesmo produto+NCM).
    Mantém o registro com melhor justificativa (da IA) e soma os usos.
    
    Returns:
        Dict com estatísticas: {'consolidados': N, 'removidos': N}
    """
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Encontrar duplicatas
            cursor.execute("""
                SELECT LOWER(TRIM(produto)) as produto_norm, ncm_codigo, COUNT(*) as qtd
                FROM classificacoes
                GROUP BY LOWER(TRIM(produto)), ncm_codigo
                HAVING COUNT(*) > 1
            """)
            
            duplicatas = cursor.fetchall()
            consolidados = 0
            removidos = 0
            
            for dup in duplicatas:
                produto_norm = dup['produto_norm']
                ncm_codigo = dup['ncm_codigo']
                
                # Buscar todos os registros duplicados
                cursor.execute("""
                    SELECT * FROM classificacoes
                    WHERE LOWER(TRIM(produto)) = ? AND ncm_codigo = ?
                    ORDER BY 
                        CASE WHEN metodo LIKE 'ia_%' THEN 0 ELSE 1 END,
                        LENGTH(justificativa) DESC,
                        validado_usuario DESC,
                        timestamp DESC
                """, (produto_norm, ncm_codigo))
                
                registros = cursor.fetchall()
                
                if len(registros) < 2:
                    continue
                
                # Primeiro registro é o "melhor" (IA com justificativa mais longa)
                principal = dict(registros[0])
                ids_remover = [dict(r)['id'] for r in registros[1:]]
                
                # Somar usos de todos os registros
                total_usos = sum(dict(r).get('usos') or 1 for r in registros)
                
                # Maior score_match
                max_score = max(dict(r).get('score_match') or 0.0 for r in registros)
                
                # Validado se qualquer um foi validado
                validado = max(dict(r).get('validado_usuario') or 0 for r in registros)
                
                # Atualizar o registro principal
                cursor.execute("""
                    UPDATE classificacoes 
                    SET usos = ?, score_match = ?, validado_usuario = ?
                    WHERE id = ?
                """, (total_usos, max_score, validado, principal['id']))
                
                # Remover duplicatas
                cursor.execute("""
                    DELETE FROM classificacoes 
                    WHERE id IN ({})
                """.format(','.join('?' * len(ids_remover))), ids_remover)
                
                consolidados += 1
                removidos += len(ids_remover)
            
            return {
                "consolidados": consolidados,
                "removidos": removidos
            }


def migrar_de_json(json_path: Path) -> int:
    """
    Migra dados do JSON antigo para SQLite
    
    Returns:
        Número de registros migrados
    """
    import json
    
    if not json_path.exists():
        print(f"⚠️ Arquivo JSON não encontrado: {json_path}")
        return 0
    
    with open(json_path, 'r', encoding='utf-8') as f:
        dados = json.load(f)
    
    if not dados:
        return 0
    
    migrados = 0
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            for reg in dados:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO classificacoes 
                        (id, timestamp, produto, ncm_codigo, ncm_descricao, confianca, 
                         metodo, justificativa, validado_usuario, classificacao_correta, 
                         ncm_corrigido, usado_treinamento)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        reg.get('id'),
                        reg.get('timestamp'),
                        reg.get('produto'),
                        reg.get('ncm_codigo'),
                        reg.get('ncm_descricao'),
                        reg.get('confianca'),
                        reg.get('metodo'),
                        reg.get('justificativa', ''),
                        int(reg.get('validado_usuario', False)),
                        int(reg.get('classificacao_correta', True)),
                        reg.get('ncm_corrigido'),
                        int(reg.get('usado_treinamento', False))
                    ))
                    migrados += 1
                except Exception as e:
                    print(f"⚠️ Erro ao migrar registro {reg.get('id')}: {e}")
    
    print(f"✅ {migrados} registros migrados de JSON para SQLite")
    return migrados


# ==================== Cache de IA ====================

def _hash_produto(produto: str) -> str:
    """Gera hash único para um produto (normalizado)"""
    import hashlib
    normalizado = produto.lower().strip()
    return hashlib.md5(normalizado.encode()).hexdigest()


def buscar_cache_ia(produto: str) -> Optional[Dict]:
    """
    Busca resposta em cache para um produto.
    
    Args:
        produto: Descrição do produto
        
    Returns:
        Dict com resposta cacheada ou None se não encontrar
    """
    produto_hash = _hash_produto(produto)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM cache_ia WHERE produto_hash = ?
        """, (produto_hash,))
        
        row = cursor.fetchone()
        if row:
            # Incrementar contador de acessos
            cursor.execute("""
                UPDATE cache_ia SET acessos = acessos + 1 WHERE produto_hash = ?
            """, (produto_hash,))
            conn.commit()
            
            return {
                "ncm_codigo": row['ncm_codigo'],
                "ncm_descricao": row['ncm_descricao'],
                "confianca": row['confianca'],
                "justificativa": row['justificativa'],
                "provider": row['provider'],
                "modelo": row['modelo'],
                "cache": True,
                "acessos": row['acessos'] + 1
            }
    
    return None


def salvar_cache_ia(
    produto: str,
    ncm_codigo: str,
    ncm_descricao: str = "",
    confianca: str = "media",
    justificativa: str = "",
    provider: str = "",
    modelo: str = ""
) -> bool:
    """
    Salva resposta da IA em cache.
    
    Args:
        produto: Descrição do produto
        ncm_codigo: NCM classificado
        ncm_descricao: Descrição do NCM
        confianca: Nível de confiança
        justificativa: Justificativa da IA
        provider: Provider usado (groq/gemini)
        modelo: Modelo usado
        
    Returns:
        True se salvou, False se já existia
    """
    produto_hash = _hash_produto(produto)
    timestamp = datetime.now().isoformat()
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO cache_ia 
                    (produto_hash, produto, ncm_codigo, ncm_descricao, confianca, justificativa, provider, modelo, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (produto_hash, produto.strip(), normalizar_ncm(ncm_codigo), ncm_descricao, confianca, justificativa, provider, modelo, timestamp))
                return True
            except sqlite3.IntegrityError:
                # Já existe - atualizar
                cursor.execute("""
                    UPDATE cache_ia 
                    SET ncm_codigo = ?, ncm_descricao = ?, confianca = ?, justificativa = ?, 
                        provider = ?, modelo = ?, timestamp = ?
                    WHERE produto_hash = ?
                """, (normalizar_ncm(ncm_codigo), ncm_descricao, confianca, justificativa, provider, modelo, timestamp, produto_hash))
                return True


def limpar_cache_ia(dias_antigos: int = 30) -> int:
    """
    Remove entradas antigas do cache.
    
    Args:
        dias_antigos: Remover entradas mais antigas que N dias
        
    Returns:
        Número de entradas removidas
    """
    from datetime import timedelta
    data_limite = (datetime.now() - timedelta(days=dias_antigos)).isoformat()
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM cache_ia WHERE timestamp < ?
            """, (data_limite,))
            return cursor.rowcount


def estatisticas_cache_ia() -> Dict:
    """Retorna estatísticas do cache de IA"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cache_ia")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(acessos) FROM cache_ia")
        total_acessos = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT provider, COUNT(*) as qtd 
            FROM cache_ia 
            GROUP BY provider
        """)
        por_provider = {row['provider']: row['qtd'] for row in cursor.fetchall()}
        
        return {
            "total_entradas": total,
            "total_acessos": total_acessos,
            "por_provider": por_provider
        }


# ==================== Sistema de Descartes ====================

def registrar_descarte(produto: str, ncm_codigo: str, motivo: str = "") -> Dict:
    """
    Registra que um NCM foi descartado para um produto específico.
    Se já existir, incrementa o contador.
    
    Returns:
        Dict com informações do descarte
    """
    ncm_limpo = normalizar_ncm(ncm_codigo)
    timestamp = datetime.now().isoformat()
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar se já existe
            cursor.execute("""
                SELECT id, contador FROM descartes 
                WHERE LOWER(TRIM(produto)) = LOWER(TRIM(?)) AND ncm_codigo = ?
            """, (produto, ncm_limpo))
            
            existente = cursor.fetchone()
            
            if existente:
                # Incrementar contador
                novo_contador = existente['contador'] + 1
                cursor.execute("""
                    UPDATE descartes 
                    SET contador = ?, timestamp = ?, motivo = ?
                    WHERE id = ?
                """, (novo_contador, timestamp, motivo, existente['id']))
                
                return {
                    "sucesso": True,
                    "mensagem": f"Descarte atualizado ({novo_contador}x)",
                    "produto": produto,
                    "ncm": ncm_limpo,
                    "contador": novo_contador,
                    "novo": False
                }
            else:
                # Inserir novo
                cursor.execute("""
                    INSERT INTO descartes (timestamp, produto, ncm_codigo, motivo, contador)
                    VALUES (?, ?, ?, ?, 1)
                """, (timestamp, produto.strip(), ncm_limpo, motivo))
                
                return {
                    "sucesso": True,
                    "mensagem": "NCM descartado para este produto",
                    "produto": produto,
                    "ncm": ncm_limpo,
                    "contador": 1,
                    "novo": True
                }


def buscar_descartes_produto(produto: str) -> List[str]:
    """
    Retorna lista de NCMs descartados para um produto específico.
    Usado para filtrar resultados de busca.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ncm_codigo FROM descartes 
            WHERE LOWER(TRIM(produto)) = LOWER(TRIM(?))
            AND contador >= 1
        """, (produto,))
        
        return [row['ncm_codigo'] for row in cursor.fetchall()]


def buscar_descartes_similares(produto: str, limite: int = 50) -> List[str]:
    """
    Retorna NCMs descartados para produtos similares (busca parcial).
    NCMs descartados múltiplas vezes para produtos similares são mais relevantes.
    """
    palavras = produto.lower().split()
    if not palavras:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar NCMs descartados onde pelo menos 2 palavras coincidem
        placeholders = " OR ".join(["LOWER(produto) LIKE ?" for _ in palavras])
        params = [f"%{p}%" for p in palavras if len(p) > 2]
        
        if not params:
            return []
        
        cursor.execute(f"""
            SELECT ncm_codigo, SUM(contador) as total_descartes
            FROM descartes 
            WHERE {placeholders}
            GROUP BY ncm_codigo
            HAVING total_descartes >= 2
            ORDER BY total_descartes DESC
            LIMIT ?
        """, (*params, limite))
        
        return [row['ncm_codigo'] for row in cursor.fetchall()]


def estatisticas_descartes() -> Dict:
    """Retorna estatísticas do sistema de descartes"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM descartes")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(DISTINCT ncm_codigo) as ncms FROM descartes")
        ncms_unicos = cursor.fetchone()['ncms']
        
        cursor.execute("SELECT COUNT(DISTINCT produto) as produtos FROM descartes")
        produtos_unicos = cursor.fetchone()['produtos']
        
        cursor.execute("""
            SELECT ncm_codigo, SUM(contador) as total 
            FROM descartes 
            GROUP BY ncm_codigo 
            ORDER BY total DESC 
            LIMIT 5
        """)
        mais_descartados = [{"ncm": r['ncm_codigo'], "vezes": r['total']} for r in cursor.fetchall()]
        
        return {
            "total_descartes": total,
            "ncms_descartados": ncms_unicos,
            "produtos_com_descarte": produtos_unicos,
            "mais_descartados": mais_descartados
        }


# ==================== CRUD NCMs ====================

def contar_ncms() -> int:
    """Retorna quantidade total de NCMs no banco"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM ncms WHERE ativo = 1")
        return cursor.fetchone()['total']


def buscar_ncm(codigo: str) -> Optional[Dict]:
    """
    Busca um NCM específico pelo código.
    Inclui termos aprendidos do histórico.
    """
    codigo_limpo = normalizar_ncm(codigo)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar dados do NCM
        cursor.execute("""
            SELECT * FROM ncms WHERE codigo = ? AND ativo = 1
        """, (codigo_limpo,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        ncm = dict(row)
        
        # Buscar termos aprendidos
        cursor.execute("""
            SELECT termo, frequencia, origem, validado 
            FROM termos_ncm 
            WHERE ncm_codigo = ?
            ORDER BY frequencia DESC, termo
        """, (codigo_limpo,))
        
        termos = [dict(r) for r in cursor.fetchall()]
        ncm['termos_aprendidos'] = [t['termo'] for t in termos]
        ncm['termos_detalhes'] = termos
        
        # Buscar termos do histórico de classificações
        cursor.execute("""
            SELECT DISTINCT produto, SUM(COALESCE(usos, 1)) as uso_total
            FROM classificacoes 
            WHERE ncm_codigo = ?
            AND (validado_usuario = 1 OR confianca = 'alta')
            GROUP BY LOWER(TRIM(produto))
            ORDER BY uso_total DESC
        """, (codigo_limpo,))
        
        termos_historico = [row['produto'] for row in cursor.fetchall()]
        
        # Combinar termos únicos
        todos_termos = list(set(ncm['termos_aprendidos'] + termos_historico))
        ncm['termos_aprendidos'] = sorted(todos_termos)
        ncm['total_termos'] = len(todos_termos)
        
        return ncm


def listar_ncms(
    capitulo: str = None,
    busca: str = None,
    limite: int = 100,
    offset: int = 0
) -> List[Dict]:
    """
    Lista NCMs com filtros opcionais.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM ncms WHERE ativo = 1"
        params = []
        
        if capitulo:
            query += " AND capitulo = ?"
            params.append(capitulo)
        
        if busca:
            query += " AND (descricao LIKE ? OR codigo LIKE ?)"
            params.extend([f"%{busca}%", f"%{busca}%"])
        
        query += " ORDER BY codigo LIMIT ? OFFSET ?"
        params.extend([limite, offset])
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def adicionar_termo_ncm(
    ncm_codigo: str,
    termo: str,
    origem: str = "classificacao",
    validado: bool = False
) -> Dict:
    """
    Adiciona ou atualiza um termo aprendido para um NCM.
    Se já existe, incrementa a frequência.
    """
    ncm_limpo = normalizar_ncm(ncm_codigo)
    termo_limpo = termo.strip()
    
    if not termo_limpo:
        return {"sucesso": False, "erro": "Termo vazio"}
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar se NCM existe
            cursor.execute("SELECT 1 FROM ncms WHERE codigo = ?", (ncm_limpo,))
            if not cursor.fetchone():
                # NCM não existe na tabela ncms, mas pode ser válido
                # Criar entrada básica
                cursor.execute("""
                    INSERT OR IGNORE INTO ncms (codigo, codigo_formatado, descricao, capitulo)
                    VALUES (?, ?, '', ?)
                """, (ncm_limpo, ncm_limpo, ncm_limpo[:2] if len(ncm_limpo) >= 2 else ''))
            
            # Tentar inserir termo, se existir incrementar frequência
            cursor.execute("""
                INSERT INTO termos_ncm (ncm_codigo, termo, origem, validado)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ncm_codigo, LOWER(TRIM(termo))) DO UPDATE SET
                    frequencia = frequencia + 1,
                    validado = CASE WHEN excluded.validado = 1 THEN 1 ELSE validado END
            """, (ncm_limpo, termo_limpo, origem, 1 if validado else 0))
            
            conn.commit()
            
            return {
                "sucesso": True,
                "ncm": ncm_limpo,
                "termo": termo_limpo,
                "origem": origem
            }


def remover_termo_ncm(ncm_codigo: str, termo: str) -> bool:
    """Remove um termo de um NCM"""
    ncm_limpo = normalizar_ncm(ncm_codigo)
    
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM termos_ncm 
                WHERE ncm_codigo = ? AND LOWER(TRIM(termo)) = LOWER(TRIM(?))
            """, (ncm_limpo, termo))
            conn.commit()
            return cursor.rowcount > 0


def buscar_ncms_por_termo(termo: str, limite: int = 10) -> List[Dict]:
    """
    Busca NCMs que têm um termo específico associado.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar nos termos aprendidos
        cursor.execute("""
            SELECT DISTINCT n.*, t.termo, t.frequencia
            FROM ncms n
            INNER JOIN termos_ncm t ON n.codigo = t.ncm_codigo
            WHERE LOWER(t.termo) LIKE LOWER(?)
            AND n.ativo = 1
            ORDER BY t.frequencia DESC
            LIMIT ?
        """, (f"%{termo}%", limite))
        
        resultados = []
        for row in cursor.fetchall():
            ncm = dict(row)
            resultados.append(ncm)
        
        # Se não encontrou nos termos, buscar na descrição
        if not resultados:
            cursor.execute("""
                SELECT * FROM ncms 
                WHERE LOWER(descricao) LIKE LOWER(?)
                AND ativo = 1
                ORDER BY codigo
                LIMIT ?
            """, (f"%{termo}%", limite))
            resultados = [dict(row) for row in cursor.fetchall()]
        
        return resultados


def sincronizar_termos_historico() -> Dict:
    """
    Sincroniza termos da tabela classificacoes para tabela termos_ncm.
    Útil para popular termos a partir do histórico existente.
    """
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar todos os pares produto/NCM validados
            cursor.execute("""
                SELECT DISTINCT produto, ncm_codigo, SUM(COALESCE(usos, 1)) as total_usos
                FROM classificacoes
                WHERE validado_usuario = 1 OR confianca = 'alta'
                GROUP BY LOWER(TRIM(produto)), ncm_codigo
            """)
            
            inseridos = 0
            atualizados = 0
            
            for row in cursor.fetchall():
                produto = row['produto']
                ncm = row['ncm_codigo']
                usos = row['total_usos']
                
                # Inserir ou atualizar termo
                cursor.execute("""
                    INSERT INTO termos_ncm (ncm_codigo, termo, frequencia, origem, validado)
                    VALUES (?, ?, ?, 'historico', 1)
                    ON CONFLICT(ncm_codigo, LOWER(TRIM(termo))) DO UPDATE SET
                        frequencia = frequencia + excluded.frequencia
                """, (ncm, produto, usos))
                
                if cursor.rowcount > 0:
                    inseridos += 1
                else:
                    atualizados += 1
            
            conn.commit()
            
            return {
                "sucesso": True,
                "termos_inseridos": inseridos,
                "termos_atualizados": atualizados
            }


def estatisticas_ncms() -> Dict:
    """Retorna estatísticas da tabela de NCMs"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM ncms WHERE ativo = 1")
        total_ncms = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM termos_ncm")
        total_termos = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(DISTINCT ncm_codigo) as ncms FROM termos_ncm")
        ncms_com_termos = cursor.fetchone()['ncms']
        
        cursor.execute("""
            SELECT capitulo, COUNT(*) as quantidade 
            FROM ncms WHERE ativo = 1 
            GROUP BY capitulo 
            ORDER BY quantidade DESC 
            LIMIT 10
        """)
        por_capitulo = [{"capitulo": r['capitulo'], "quantidade": r['quantidade']} for r in cursor.fetchall()]
        
        return {
            "total_ncms": total_ncms,
            "total_termos_aprendidos": total_termos,
            "ncms_com_termos": ncms_com_termos,
            "distribuicao_capitulos": por_capitulo
        }


# ==================== Tabelas de Usuário ====================

def _criar_tabelas_usuario(conn):
    """Cria tabelas de classificações e descartes por usuário"""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classificacoes_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT NOT NULL,
            classificacao_id TEXT NOT NULL,
            produto TEXT NOT NULL,
            ncm_codigo TEXT NOT NULL,
            ncm_descricao TEXT,
            score_match REAL DEFAULT 0.0,
            metodo TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (classificacao_id) REFERENCES classificacoes(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_classif_usuario_id
        ON classificacoes_usuario(usuario_id)
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_classif_usuario_unico
        ON classificacoes_usuario(usuario_id, LOWER(TRIM(produto)), ncm_codigo)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS descartes_usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT NOT NULL,
            produto TEXT NOT NULL,
            ncm_codigo TEXT NOT NULL,
            motivo TEXT,
            contador INTEGER DEFAULT 1,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_descartes_usuario_id
        ON descartes_usuario(usuario_id)
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_descartes_usuario_unico
        ON descartes_usuario(usuario_id, LOWER(TRIM(produto)), ncm_codigo)
    """)

    conn.commit()


def inserir_classificacao_usuario(
    usuario_id: str,
    classificacao_id: str,
    produto: str,
    ncm_codigo: str,
    ncm_descricao: str = "",
    score_match: float = 0.0,
    metodo: str = ""
) -> Dict:
    """Registra classificação aceita para um usuário específico"""
    timestamp = datetime.now().isoformat()
    ncm_norm = normalizar_ncm(ncm_codigo)

    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO classificacoes_usuario
                    (usuario_id, classificacao_id, produto, ncm_codigo, ncm_descricao, score_match, metodo, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (usuario_id, classificacao_id, produto.strip(), ncm_norm, ncm_descricao, score_match, metodo, timestamp))
            except sqlite3.IntegrityError:
                # Já existe — atualizar timestamp
                cursor.execute("""
                    UPDATE classificacoes_usuario
                    SET classificacao_id = ?, score_match = ?, metodo = ?, timestamp = ?
                    WHERE usuario_id = ? AND LOWER(TRIM(produto)) = LOWER(TRIM(?)) AND ncm_codigo = ?
                """, (classificacao_id, score_match, metodo, timestamp, usuario_id, produto.strip(), ncm_norm))

    return {
        "usuario_id": usuario_id,
        "classificacao_id": classificacao_id,
        "produto": produto.strip(),
        "ncm_codigo": ncm_norm,
        "ncm_descricao": ncm_descricao,
        "timestamp": timestamp
    }


def listar_classificacoes_usuario(usuario_id: str, limite: int = 100) -> List[Dict]:
    """Retorna classificações aceitas de um usuário"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM classificacoes_usuario
            WHERE usuario_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (usuario_id, limite))
        return [dict(row) for row in cursor.fetchall()]


def registrar_descarte_usuario(
    usuario_id: str,
    produto: str,
    ncm_codigo: str,
    motivo: str = ""
) -> Dict:
    """Registra descarte para um usuário específico"""
    ncm_limpo = normalizar_ncm(ncm_codigo)
    timestamp = datetime.now().isoformat()

    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, contador FROM descartes_usuario
                WHERE usuario_id = ? AND LOWER(TRIM(produto)) = LOWER(TRIM(?)) AND ncm_codigo = ?
            """, (usuario_id, produto, ncm_limpo))

            existente = cursor.fetchone()
            if existente:
                novo_cont = existente['contador'] + 1
                cursor.execute("""
                    UPDATE descartes_usuario
                    SET contador = ?, timestamp = ?, motivo = ?
                    WHERE id = ?
                """, (novo_cont, timestamp, motivo, existente['id']))
                return {"usuario_id": usuario_id, "ncm": ncm_limpo, "contador": novo_cont}
            else:
                cursor.execute("""
                    INSERT INTO descartes_usuario (usuario_id, produto, ncm_codigo, motivo, contador, timestamp)
                    VALUES (?, ?, ?, ?, 1, ?)
                """, (usuario_id, produto.strip(), ncm_limpo, motivo, timestamp))
                return {"usuario_id": usuario_id, "ncm": ncm_limpo, "contador": 1}


def listar_descartes_usuario(usuario_id: str, limite: int = 100) -> List[Dict]:
    """Retorna descartes de um usuário"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM descartes_usuario
            WHERE usuario_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (usuario_id, limite))
        return [dict(row) for row in cursor.fetchall()]


def deletar_classificacao_usuario(usuario_id: str, classificacao_id: str) -> bool:
    """Remove classificação do registro do usuário"""
    with _db_lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM classificacoes_usuario
                WHERE usuario_id = ? AND classificacao_id = ?
            """, (usuario_id, classificacao_id))
            return cursor.rowcount > 0


# Inicializar banco ao importar módulo
inicializar_banco()

# Criar tabelas de usuário (migração segura)
with get_connection() as _conn:
    _criar_tabelas_usuario(_conn)
