---
name: newsletter-voice
description: >
  Monta as instruções de escrita de newsletter dentro de um projeto. Roda depois do voice-builder. Produz o arquivo newsletter-voice.md, um único arquivo que sua {{AGENTE_NAME}} consulta toda vez que escreve uma newsletter na voz do dono. Funciona com ou sem edições anteriores de newsletter: se o dono tem edições passadas, a skill analisa elas; se não tem, a skill oferece 6 arquétipos ajustados à voz do dono. Use sempre que o dono disser "monta minha voz de newsletter", "aprende meu estilo de newsletter", "configura meu sistema de newsletter", "treina nas minhas newsletters", "onboarding de newsletter", ou colar exemplos de newsletter no chat pedindo uma análise. Exige que o voice-builder tenha rodado antes: a skill precisa dos arquivos voice.md e about-me.md no projeto pra funcionar.
---

# Voz de Newsletter

## Checagem de pré-requisitos

No momento em que esta skill for acionada, verifique a raiz do projeto procurando voice.md e about-me.md.

Se qualquer um dos arquivos estiver faltando, diga pro dono:

> A voz de newsletter fica em cima do seu perfil de voz geral. Rode o voice-builder primeiro (suba a skill ou diga "monta minha voz") e volte aqui depois que about-me.md e voice.md estiverem no projeto.

Aí pare. Não continue enquanto os dois arquivos não existirem.

Se os dois arquivos existirem, leia ambos por completo e vá direto pro Passo 1.

## Passo 1. Verificar se há exemplos

Pergunte pro dono no chat:

> Você tem 2 ou 3 edições passadas de newsletter pra eu aprender com elas?
>
> Sim: cole elas aqui (uma por mensagem ou todas de uma vez)
> Não: digite "arquétipo" e eu monto a partir de um modelo ajustado à sua voz

Espere a resposta.

Se o dono colar 2 ou mais newsletters, vá pro Passo 2a.
Se o dono digitar "arquétipo", vá pro Passo 2b.
Se o dono colar 1 newsletter só, peça pelo menos mais uma. Se ele só tiver uma, ofereça: "Um exemplo só não dá pra detectar padrão. Quer que eu mude pro modo arquétipo e use essa sua newsletter como ponto de referência?"

## Passo 2a. Análise baseada em exemplos

Leia cada newsletter por completo. Procure padrões que se repetem entre as edições, não manias pontuais de uma só. Extraia:

**Fórmula de abertura**
- O que as 3 primeiras frases fazem (resultado específico, observação cultural, afirmação, cena, pergunta)
- Tamanho do trecho de abertura antes da primeira quebra estrutural
- Movimento de credibilidade (como o autor estabelece autoridade logo no começo)
- Promessa de valor (o que o leitor é avisado que vai ganhar)

**Estrutura de seções**
- Montagem do problema ou contraste
- Framework nomeado ou prosa livre
- Passos numerados, métodos ou argumento contínuo
- Padrões de exemplos e evidências
- Seção de bônus ou extensão
- Fórmula de fechamento e assinatura

**Filosofia de dados**
- Números específicos por edição (conte eles)
- Estilo de atribuição de fonte (com link, citada pelo nome, sem crédito)
- Proporção entre exemplo e abstração
- Reconhecimento de limitações ou falhas

**Formatação**
- Uso de cabeçalhos (frequência, hierarquia)
- Uso de listas (numeradas, com marcadores, com setas)
- Uso de negrito e itálico
- Formatação de prompt, bloco de código ou citação
- Marcadores visuais (setas, check, emojis se houver)

**Tamanho**
- Faixa de contagem de palavras entre os exemplos
- Contagem de palavras por seção

**Marcas de voz próprias do formato newsletter**
- Dicas ou destaques (frequência, formato)
- Fechamentos voltados pro futuro
- Frase de assinatura, se for consistente entre os exemplos
- Meta-transparência (o autor reflete sobre o processo ou pede feedback)

**Sinais de ausência**
- Palavras, construções ou estruturas que faltam em todos os exemplos
- Movimentos de fechamento que o autor nunca usa
- Assuntos que o autor nunca toca

Aí vá pro Passo 3.

## Passo 2b. Seleção de arquétipo

Chame a ferramenta AskUserQuestion com uma única pergunta:

```json
[
  {
    "question": "Qual arquétipo de newsletter combina com o que você quer escrever?",
    "header": "Arquétipo",
    "multiSelect": false,
    "options": [
      {"label": "Tutorial com dados", "description": "Números, frameworks, métodos passo a passo com prompts"},
      {"label": "Ensaio contrário", "description": "Tome uma posição, defenda ela, nomeie a oposição"},
      {"label": "Dissecação de caso", "description": "Um assunto por edição, destrinchado a fundo"},
      {"label": "Digest curado", "description": "5 a 7 links com o seu comentário em cada um por semana"},
      {"label": "Ensaio pessoal", "description": "Reflexão sobre um tema, história primeiro"},
      {"label": "Entrevista ou perfil", "description": "Uma pessoa por edição, em formato pergunta e resposta ou narrativa"}
    ]
  }
]
```

Depois que o dono escolher um arquétipo, carregue os padrões correspondentes de `references/archetypes.md` dentro desta pasta de skill. Ajuste cada campo usando voice.md e about-me.md antes de escrever newsletter-voice.md. Sinalize dentro do arquivo de saída que os padrões de arquétipo foram usados e que o arquivo deve ser revisitado depois de 5 edições publicadas.

## Passo 3. Escrever newsletter-voice.md

Crie newsletter-voice.md na raiz do projeto. Arquivo único, meta de 800 a 1.200 palavras. Use esta estrutura:

```
# Voz de Newsletter

## Origem
[Baseada em exemplos: analisei X edições de newsletter] OU [Baseada em arquétipo: [nome do arquétipo] ajustado ao voice.md. Revisitar depois de 5 edições publicadas.]

## Público e propósito
[Quem lê esta newsletter e o que tira dela. Escrito a partir do about-me.md e do voice.md. 2 a 3 frases.]

## Princípios de voz
[3 a 5 princípios centrais que a escrita sempre mantém. Cada um uma frase curta e afirmativa. Ajustado à voz deste dono no voice.md.]

## Fórmula de abertura
[Como as edições começam. Inclua 2 modelos concretos com marcadores entre colchetes, ex.: "[Resultado específico com número]. [Marca de credibilidade]. [Promessa de valor desta edição]." Meta de contagem de palavras pro trecho de abertura.]

## Fluxo de seções
[Estrutura padrão de uma edição, seção por seção, no máximo 5 a 8 seções. Notas breves sobre o que cada seção faz e quanto tempo dura.]

## Dados e evidências
[Como números e exemplos são usados. Regras específicas, ex.: "toda afirmação precisa de um número", "fontes com link no texto", "proporção entre exemplo e abstração de mais ou menos 3 pra 1".]

## Regras de formatação
[Cabeçalhos, listas, negrito, itálico, blocos de código, marcadores visuais. O que usar, o que evitar. Tirado dos exemplos ou dos padrões de arquétipo.]

## Fechamento e assinatura
[Como as edições terminam. Frase voltada pro futuro versus resumo. Frase de assinatura se houver uma consistente entre os exemplos (não invente uma).]

## O que esta newsletter nunca faz
[1 parágrafo curto ou 3 a 5 itens. Tirado dos padrões de ausência entre os exemplos ou dos padrões de arquétipo. Só comportamentos, não uma lista de palavras proibidas.]

## Tamanho
[Meta de contagem de palavras pras edições padrão. Meta separada pros guias mais longos e completos se o dono escreve os dois formatos.]
```

Preencha cada seção a partir dos exemplos (ou dos padrões de arquétipo ajustados). Sem encheção de linguiça genérica. Se os exemplos não cobrirem algo, escreva "sem padrão claro entre os exemplos" em vez de chutar.

## Passo 4. Confirmar e passar adiante

Diga pro dono:

> Sua voz de newsletter está montada. O newsletter-voice.md está na raiz do seu projeto, junto com about-me.md e voice.md. Quando você quiser escrever uma edição, diga "escreve uma newsletter" e eu uso os três arquivos juntos.
>
> [Se for modo arquétipo: Lembre que este arquivo foi montado a partir de padrões de arquétipo. Depois de umas 5 edições publicadas, rode esta skill de novo com seus exemplos reais pra ter um perfil mais afiado.]

## O que esta skill produz

Um arquivo na raiz do projeto:

- newsletter-voice.md: instruções de escrita específicas de newsletter cobrindo público, princípios de voz, fórmula de abertura, fluxo de seções, filosofia de dados, formatação, fechamento, padrões de ausência e metas de tamanho

## Regras

- Exija voice.md e about-me.md na raiz do projeto antes de rodar. Pare e redirecione pro voice-builder se algum estiver faltando.
- Mínimo de 2 exemplos de newsletter se o dono escolher o modo baseado em exemplos. Ofereça o modo arquétipo se houver menos.
- Mantenha o newsletter-voice.md abaixo de 1.200 palavras. Enxuto vence exaustivo.
- Não invente sinais de voz. Trabalhe só a partir dos exemplos ou dos padrões de arquétipo ajustados ao voice.md.
- Não duplique conteúdo do voice.md. Referencie ele onde for relevante. O newsletter-voice.md acrescenta só regras específicas de newsletter.
- Não embuta os nomes específicos, URLs ou frases de assinatura do dono a menos que apareçam de forma consistente em 2 ou mais exemplos.
- Não produza um arquivo separado de voz ou de palavras proibidas. Os padrões de ausência ficam dentro do newsletter-voice.md como uma única seção.
- Português do Brasil natural e fluido em tudo.
- Nunca use travessões em nenhum arquivo de saída nem em nenhum rascunho.
