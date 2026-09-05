---
name: niche-research
description: >
  Levanta as 20 histórias mais relevantes de um nicho nos últimos 7 dias usando um navegador com IA. Datas verificadas, links reais, ângulos prontos pra compartilhar. Sua {{AGENTE_NAME}} dirige o navegador pra rolar o feed do Reddit, do X e rodar buscas no Google, exatamente como um pesquisador humano faria. Use esta skill sempre que o dono pedir "pesquisa meu nicho", "o que tá em alta", "acha histórias", "as notícias da semana", "pesquisa de conteúdo", ou jogar um nicho e perguntar o que está rolando nele. Precisa de um navegador com IA habilitado pra navegação ao vivo.
---

# Pesquisa de Nicho

## CRÍTICO: começa sozinha ao carregar

Quando esta skill disparar, vá direto pro Passo 1. Não resuma o método de pesquisa.

## Pré-requisitos

Esta skill precisa de navegação ao vivo. Use esta ordem de preferência:

1. **Navegador com IA** (preferido). Confira se o navegador com IA está habilitado e se a {{AGENTE_NAME}} tem permissão pra navegar na aba atual. Se não tiver, avise o dono:
   > Habilite o navegador com IA e abra uma aba em branco. Preciso dirigir o navegador pra rolar Reddit, X e rodar buscas no Google com datas verificadas.
2. **Playwright MCP** como alternativa se o navegador com IA não estiver disponível.
3. **Ferramentas de busca e leitura na web** como último recurso (menos completas na rolagem de feed).

Escolha o melhor caminho disponível e siga.

## Passo 1. Levantar o nicho

Chame AskUserQuestion:

```json
[
  {
    "question": "Qual nicho você quer pesquisar?",
    "header": "Nicho",
    "multiSelect": false,
    "options": [
      {"label": "Vou digitar meu nicho", "description": "Digite a frase exata do nicho depois desta resposta"},
      {"label": "Pegar do about-me.md", "description": "Usar o nicho e o público que já estão nos meus arquivos de voz"}
    ]
  }
]
```

Se o dono escolher "Pegar do about-me.md", leia o arquivo na raiz do projeto. Se o arquivo não existir ou não trouxer um nicho claro, volte a pedir pro dono digitar.

## Passo 2. Navegar como um pesquisador humano

Dirija o navegador por estas ações, nesta ordem. Verifique a data de publicação de cada item. Exclua sem exceção qualquer coisa com mais de 7 dias a partir de hoje.

### 2a. Varredura do feed do Reddit

1. Navegue até https://www.reddit.com/ (feed da home).
2. Role o feed. Carregue mais posts.
3. Abra os posts relevantes pro nicho. Em cada post, confira o carimbo de "postado há X dias".
4. Descarte posts com mais de 7 dias.
5. Repita com https://www.reddit.com/r/popular/.
6. Pesquise também qualquer subreddit específico do nicho que apareça enquanto você rola.

### 2b. Varredura do feed do X (Twitter)

1. Navegue até https://x.com/home (feed Para Você).
2. Role várias telas.
3. Abra as threads inteiras dos tweets relevantes pro nicho.
4. Confira o carimbo de data em cada thread.
5. Descarte posts com mais de 7 dias, mesmo que o engajamento esteja alto.

### 2c. Busca na web pelo Google

Rode estas buscas uma a uma, abra os primeiros resultados e verifique as datas de publicação.

- `[nicho] notícias` (em Ferramentas → Qualquer data → Última semana)
- `[nicho] lançamento` (última semana)
- `[nicho] polêmica` (última semana)
- `[nicho] pesquisa` (última semana)
- `[nicho] regulação` (última semana)

Pra cada resultado promissor:

1. Abra a página.
2. Localize a data de publicação visível.
3. Confirme que está dentro dos últimos 7 dias.
4. Se a data estiver faltando, confusa ou com mais de 7 dias, exclua.

## Passo 3. Sintetizar em temas

Junte um conjunto amplo de itens verificados e dentro da janela. Agrupe itens relacionados em temas. Cada tema pode combinar discussão nas redes e cobertura jornalística.

Selecione temas que mostrem pelo menos dois destes sinais:

- Atenção ou discussão forte
- Discordância ou debate claro
- Informação nova ou insight inédito
- Implicações reais pro nicho

Mire em 20 temas. Menos é aceitável se o material for genuinamente limitado.

## Passo 4. Saída

Primeira linha antes da tabela:

```
Em [DD/MM/AAAA]
```

Depois, uma tabela em markdown com exatamente estas colunas:

```
| Tema / História emergente | Plataformas (Reddit, X, Notícias) | Principais comunidades / contas / fontes | Links representativos | Sinais de atenção | O que está acontecendo ou sendo debatido | Por que importa pro [NICHO] | Ângulo pra compartilhar |
```

Nada de texto fora da tabela.

## Passo 5. Oferecer o próximo passo

Depois da tabela, pergunte:

> Tem alguma linha aqui que você quer que eu transforme num post de LinkedIn? Chame a skill post-writer com o número da linha, ou a skill post-formatter pra aplicar um framework.

## Regras

- Nunca invente links, métricas ou datas.
- Exclua sem exceção qualquer coisa com mais de 7 dias.
- Verifique cada data de publicação antes de incluir um item. Sem atalhos.
- Só a tabela no final. Sem comentário, sem parágrafo de resumo.
- Se passarem menos de 20 temas no filtro, diga isso. Não encha com itens fracos.
- Se o navegador com IA não estiver disponível e nem o Playwright MCP nem as ferramentas de busca derem conta da rolagem de feed direito (Reddit e X), diga ao dono o que está faltando em vez de fingir a varredura.
- Português do Brasil o tempo todo. Formato de data DD/MM/AAAA.
- Nunca use travessões.
