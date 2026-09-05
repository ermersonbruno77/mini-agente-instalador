# Pipeline de 3 Etapas para Tarefas de Código

> Combinado com o dono em **2026-04-29** após bronca de "bate-bola achei resolvi" sem testar de verdade. Pipeline obrigatório toda vez que o assunto for código (backend, frontend, deploy, scripts, refator, fix, feature).

---

## Resumo Visual

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  ETAPA 1            │    │  ETAPA 2            │    │  ETAPA 3            │
│  Análise &          │ →  │  Execução           │ →  │  Checagem & QA      │
│  Planejamento       │    │  (1 ou N Paulos)    │    │  (1-3 Paulos QA)    │
│  (1 Paulo Analista) │    │                     │    │                     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
        plano                  código entregue              validado ponta a ponta
                                                              ↓
                                                         Notifica dono
```

**Nada chega ao dono sem passar pela Etapa 3.**

---

## Etapa 1 — Análise & Planejamento

**Quem:** 1 Paulo Analista (subagente paulo-dev em modo análise)
**O que faz:**
- Mapeia o cenário atual (estado do código, deps, infra envolvida)
- Lista probabilidades de causa-raiz, se for bug
- Monta plano de execução com escopo claro
- Identifica arquivos afetados, riscos, tempo estimado

**O que NÃO faz:**
- Não toca em código
- Não executa nada
- Não faz commits

**Saída:** Plano detalhado contendo:
- Etapas numeradas e ordenadas
- Lista de arquivos que vão ser tocados
- Riscos identificados
- Tempo estimado total

**Exemplo de saída esperada:**

```
PLANO — Fix do 403 Acesso Negado pós-login no CRM Exemplo

Causa-raiz mais provável:
- Caddy roteia /api/v1/profile pro container CRM (porta interna) em vez do auth-service (porta interna)
- CRM não valida JWT issued pelo auth → 401 → frontend redireciona pra /unauthorized

Etapas:
1. Verificar Caddyfile — ver ordem das rotas /api/v1/*
2. Adicionar handle blocks pra /profile, /permissions, /resource_actions, /mfa antes do catch-all
3. caddy validate + systemctl reload caddy
4. Curl-test: login → cookie → GET /profile com Bearer

Arquivos: /etc/caddy/Caddyfile (servidor de produção)
Riscos: ordem de handlers no Caddy é literal — bloco mal posicionado quebra outras rotas
Tempo: 5-10 min
```

---

## Etapa 2 — Execução

**Quem:** 1 Paulo executor OU N Paulos em paralelo (depende do tamanho)

**Regra de divisão:**
- Tarefa pequena (1 arquivo, 1 frente): **1 Paulo**
- Tarefa grande/multi-frente: **N Paulos em paralelo**, com escopos isolados (sem conflito de arquivos)

**O que faz:**
- Pega o plano da Etapa 1 e executa exatamente
- Se aparecer divergência do plano (algo inesperado), reporta de volta antes de improvisar
- Cada Paulo entrega o trabalho + reporta o que fez

**Exemplos de paralelização:**

| Tarefa | Como dividir |
|---|---|
| Site landing page com 8 seções | 1 Paulo por bloco de seções, sem sobrepor `<section>` |
| Migração de 5 endpoints da v1 pra v2 | 1 Paulo por endpoint |
| Fix bug ponto único | 1 Paulo só |
| Refatorar serviço inteiro | 1 Paulo (não paraleliza, conflito alto) |

**O que NÃO faz:**
- Paulo executor **NÃO testa o que entregou**. Confia no plano e entrega.
- Não notifica o dono direto.

---

## Etapa 3 — Checagem & QA

**Quem:** 1, 2 ou 3 Paulos QA, dependendo do tamanho do entregável.

**O que faz:**
- Testa de verdade. Não confia no que o Paulo executor disse.
- Métodos por tipo de entrega:

| Tipo de entrega | Como testa |
|---|---|
| Endpoint backend | curl com payload real, valida status + body |
| Frontend (UI) | Browser headless (Playwright), screenshot, valida elementos visíveis |
| Deploy | Curl no domínio público, verifica HTTP 200 + cabeçalhos esperados |
| Script CLI | Roda com input real, verifica output |
| Migração de banco | psql, conta linhas antes/depois, verifica schema |
| Bug fix | Reproduz o bug original e confirma que não acontece mais |
| CSS/visual | Screenshot + comparação com referência |

**Saída:**
- ✅ OK + lista do que foi testado
- ❌ Lista de problemas reais encontrados → volta pra Etapa 2 com correções

**Só notifico o dono DEPOIS que a Etapa 3 passou.**

---

## Regras Rígidas

1. **Toda tarefa de código passa pelas 3 etapas.** Sem exceção pra "rapidinha".

2. **Exceção parcial:** fix trivial (1 caractere, typo, espaço a mais) pode pular Etapa 1, mas **Etapa 3 é obrigatória sempre**.

3. **Nunca assumir que o Paulo executor testou.** Paulo QA é sempre separado, com contexto próprio.

4. **Nunca notificar o dono antes da Etapa 3 passar.**

5. **Se a Etapa 3 falhar:** volta pra Etapa 2 com lista de problemas. Nada chega no dono até passar de novo.

6. **Comunicação durante execução:** se passar de 5 min sem update, mando status intermediário no Telegram.

---

## Origem da Regra

**Data:** 2026-04-29

**Contexto:** dono deu bronca depois de eu falar várias vezes "achei, resolvi" e ele abrir o resultado e estar quebrado.

**Bronca exata:** *"se tem uma coisa que eu odeio é quando vc fica nesse bate bola de 'achei, resolvi'"*

**Solução acordada:** Pipeline de 3 etapas, com Paulo QA dedicado separado do Paulo executor, garantindo que qualidade vem antes da entrega. Eliminação total do "achei resolvi" sem teste real.

---

## Cheat Sheet (cola rápida)

| Pergunta | Resposta |
|---|---|
| Tarefa pequena de 1 linha. Pula Etapa 1? | Sim |
| Tarefa pequena de 1 linha. Pula Etapa 3? | **NÃO. Nunca.** |
| Posso entregar antes do Paulo QA validar? | **NÃO** |
| Quantos Paulos QA usar? | 1 (pequeno), 2 (médio), 3 (grande/crítico) |
| Paulo executor pode também ser Paulo QA? | **NÃO**, sempre separado |
| Etapa 3 falhou. Próximo passo? | Volta Etapa 2 com correções, refaz Etapa 3 |
| Update intermediário pro dono? | A cada 5 min se ainda em execução |

---

