# Database Schema — {{AGENTE_NAME_LOWERCASE}}_memory

Schema do banco PostgreSQL usado pelo agente (memoria vetorial, delegacao a subagente,
promessas, lembretes). Fork sanitizado de uma base de producao real; as tabelas de
SDR/DM/analytics do template original ficaram, sem uso, caso um fork futuro precise
delas — o time deste fork nao usa.

- **Engine**: PostgreSQL 14+ (testado em 14.22)
- **Extensao obrigatoria**: `pgvector`
- **Arquivo**: `schema.sql` (DDL apenas, sem dados, sanitizado)
- **Embeddings**: 384 dimensoes, geradas pelo servico local `{{AGENTE_NAME_LOWERCASE}}-memory`
  (porta 3007, `/embed`), **nao** pela API da OpenAI. Se algum dia trocar de provedor de
  embedding, mude a dimensao da coluna `vector(N)` pra bater com o novo modelo, senao todo
  INSERT falha por incompatibilidade de tamanho.
- **Tabelas novas neste fork**: `agente_atividade`, `agente_atividade_passo`, `promessas`,
  `lembretes` — nao existiam no dump original, foram acrescentadas no fim do `schema.sql`
  pra bater com o que `tools/agente_log.py`, `tools/promessas.py` e
  `tools/lembretes_check.py` esperam.

## Como aplicar o schema

### 1. Pre-requisitos

- PostgreSQL 14+ instalado e rodando
- Extensao `pgvector` instalada no servidor (`apt install postgresql-14-pgvector` em Ubuntu, ou via source)
- Usuario com permissao `CREATE DATABASE` e `CREATE EXTENSION`

### 2. Criar banco e extensao

```bash
# Criar database (ajuste o usuario conforme seu ambiente)
createdb -h 127.0.0.1 -U postgres {{AGENTE_NAME_LOWERCASE}}_memory

# Habilitar pgvector dentro do banco recem-criado
psql -h 127.0.0.1 -U postgres -d {{AGENTE_NAME_LOWERCASE}}_memory -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. Aplicar o schema

```bash
psql -h 127.0.0.1 -U postgres -d {{AGENTE_NAME_LOWERCASE}}_memory -f schema.sql
```

### 4. Validar

```bash
psql -h 127.0.0.1 -U postgres -d {{AGENTE_NAME_LOWERCASE}}_memory -c "\dt"
# Deve listar as tabelas originais MAIS agente_atividade, agente_atividade_passo,
# promessas e lembretes
```

## Tabelas agrupadas por dominio

### Memoria e contexto (4 tabelas)

Sao o cerebro vetorial do agente. Embeddings de 1536 dimensoes (text-embedding-3-small da OpenAI).

| Tabela | Funcao | Volume prod |
|---|---|---|
| `conversation_history` | Historico completo de mensagens user/agent (com embedding) | ~30k linhas |
| `memory_chunks` | Chunks indexados de arquivos `knowledge/` e `memory/` | ~6k linhas |
| `memory_facts` | Fatos curtos extraidos manualmente (ancoras semanticas) | ~50 linhas |
| `transcript_chunks` | Chunks de transcricoes de calls indexados | 0 linhas |

### Sessoes e transcricoes (4 tabelas)

| Tabela | Funcao | Volume prod |
|---|---|---|
| `session_transcripts` | Transcricoes brutas de sessoes Telegram/CLI | ~1.7k linhas |
| `conversation_transcripts` | Conversas consolidadas (cron 2h) | 0 linhas |
| `session_checkpoints` | Checkpoints de retomada de contexto | 0 linhas |
| `sync_status` | Status de sincronizacao entre processos | ~330 linhas |

### Direct Messages Instagram (2 tabelas)

| Tabela | Funcao | Volume prod |
|---|---|---|
| `dm_conversations` | Mensagens trocadas com leads via DM | ~9.6k linhas |
| `dm_contact_profiles` | Perfis enriquecidos dos contatos | ~1.2k linhas |

### SDR e vendas (4 tabelas)

Sistema de agentes SDR (Davi, Lucas, Felipe, etc).

| Tabela | Funcao | Volume prod |
|---|---|---|
| `sdr_agents` | Configuracao dos agentes SDR | 3 linhas |
| `sdr_agent_files` | Arquivos de conhecimento por agente | 2 linhas |
| `sdr_channels` | Canais conectados (WhatsApp, IG, etc) | 0 linhas |
| `sdr_agent_sales` | Vendas registradas por agente | ~350 linhas |
| `sdr_cart_abandonments` | Carrinhos abandonados rastreados | ~240 linhas |

### Analytics (1 tabela, herdada, sem uso neste fork)

| Tabela | Funcao |
|---|---|
| `site_analytics` | Eventos de tracking de sites/landing pages |

### Delegacao, promessas e lembretes (4 tabelas, novas neste fork)

Sao o que faz o `CLAUDE.md` e os agentes deste fork funcionarem de verdade — sem elas,
`tools/agente_log.py`, `tools/promessas.py` e `tools/lembretes_check.py` falham.

| Tabela | Funcao |
|---|---|
| `agente_atividade` | Registro de cada delegacao a subagente (inicio, fim, resultado, tokens) |
| `agente_atividade_passo` | Passo intermediario de uma atividade ainda aberta |
| `promessas` | Toda promessa de trabalho futuro, com prazo e prova de entrega exigida |
| `lembretes` | Lembrete agendado que o cron dispara quando vence |

## Top tabelas por volume

1. `conversation_history` - 29.718
2. `dm_conversations` - 9.583
3. `memory_chunks` - 6.081
4. `session_transcripts` - 1.748
5. `dm_contact_profiles` - 1.237
6. `site_analytics` - 766
7. `sdr_agent_sales` - 351
8. `sync_status` - 328

## Notas importantes

- **Schema apenas, sem dados**: o arquivo `schema.sql` contem somente DDL (CREATE TABLE, INDEX, SEQUENCE, FUNCTION). Para popular um ambiente novo voce vai precisar de seeds proprios.
- **Embeddings 1536 dim**: tabelas com coluna `embedding vector(1536)` exigem que voce gere os embeddings via OpenAI `text-embedding-3-small` para indexar conteudo novo.
- **Indice HNSW**: as buscas semanticas (latencia <50ms em 30k+ vetores) usam indices HNSW criados no schema.
- **User**: o dump foi feito com `--no-owner --no-privileges` entao o schema e neutro, voce pode aplicar com qualquer usuario PostgreSQL.

## Referencia para regerar

Caso o schema mude em producao, regere com:

```bash
ssh root@{{VPS_IP}} "PGPASSWORD=*** pg_dump -h 127.0.0.1 -U {{AGENTE_NAME_LOWERCASE}} -s --no-owner --no-privileges --no-comments {{AGENTE_NAME_LOWERCASE}}_memory" > schema.sql
# E remova manualmente as linhas \restrict / \unrestrict no inicio e fim, se existirem
```
