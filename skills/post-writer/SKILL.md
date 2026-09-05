---
name: post-writer
description: >
  Escreve posts pra rede social no mesmo estilo de voz do dono (about-me.md e voice.md). Use esta skill sempre que o dono pedir "escreve um post", "rascunha um post", "post pra rede social", "post sobre [tema]", "ideia de conteúdo" ou qualquer ajuda pra escrever conteúdo pra rede social. Dispare também quando o dono colar um monte de contexto (anotações, transcrições, tópicos) e quiser transformar isso num post. Sempre consulte os arquivos de voz do projeto antes de escrever. Sempre entregue o post final dentro de um bloco de código.
---

# Post Writer

## CRÍTICO: começa sozinha ao carregar

No instante em que esta skill dispara, vá direto pro Passo 1. Não resuma a skill. Não explique o que ela faz. Não liste os arquivos que ela consulta. Pule pra coleta de informações na hora.

## Passo 1. Coletar as informações

Procure no projeto os arquivos about-me.md e voice.md. Leia os dois. Se faltar algum, avise o dono pra rodar primeiro a skill de construção de voz ("fala: monta minha voz") e pare por aqui.

Se os dois arquivos existem, chame o AskUserQuestion com este JSON exato:

```json
[
  {
    "question": "Sobre qual tema você quer postar?",
    "header": "Tema",
    "multiSelect": false,
    "options": [
      {"label": "Colar um monte de contexto", "description": "Tenho anotações, transcrições ou ideias soltas pra virar post"},
      {"label": "Tenho um tema em mente", "description": "Vou digitar o tema depois disso"},
      {"label": "Sugere temas pra mim", "description": "Com base no meu sistema de voz, sugere 5 temas pra eu postar"}
    ]
  },
  {
    "question": "Você tem algum post de referência pra eu usar como inspiração de estrutura?",
    "header": "Referências",
    "multiSelect": false,
    "options": [
      {"label": "Sem referências", "description": "Escreve do zero usando só meus arquivos de voz"},
      {"label": "Vou colar exemplos", "description": "Tenho posts de outros criadores pra você estudar antes"},
      {"label": "Usa meus posts de treino", "description": "Usa de referência os posts que usei na construção de voz"}
    ]
  }
]
```

Com base nas respostas:
- "Colar um monte de contexto": espere o dono colar, extraia a ideia central e siga pro Passo 2
- "Tenho um tema em mente": espere o dono digitar e siga pro Passo 2
- "Sugere temas pra mim": leia os pilares de tema do about-me.md e o voice.md, sugira 5 temas específicos com um ângulo de uma linha pra cada e depois use o AskUserQuestion pra deixar o dono escolher um
- "Vou colar exemplos": espere os posts de referência, anote os padrões de estrutura e siga em frente
- "Usa meus posts de treino": use de referência os posts que já estão no projeto

## Passo 2. Pesquisar e planejar

Antes de escrever, pesquise o tema. Procure:
- Dados ou estatísticas que sustentem o ângulo
- Visões contrárias ou fatos surpreendentes
- Exemplos reais ou estudos de caso
- Crenças equivocadas comuns pra contestar

Depois apresente um plano de post. Chame o AskUserQuestion:

```json
[
  {
    "question": "Qual ângulo funciona melhor pra este post?",
    "header": "Ângulo",
    "multiSelect": false,
    "options": [
      {"label": "[Nome do ângulo 1]", "description": "[Uma frase descrevendo o ângulo e o gancho]"},
      {"label": "[Nome do ângulo 2]", "description": "[Uma frase descrevendo o ângulo e o gancho]"},
      {"label": "[Nome do ângulo 3]", "description": "[Uma frase descrevendo o ângulo e o gancho]"}
    ]
  },
  {
    "question": "Qual framework você quer?",
    "header": "Framework",
    "multiSelect": false,
    "options": [
      {"label": "PAS", "description": "Problema, Agitação, Solução"},
      {"label": "Lista de como fazer", "description": "Passos ou dicas numeradas"},
      {"label": "História com lição", "description": "História pessoal com um aprendizado"},
      {"label": "Visão contrária", "description": "Contestar uma crença comum"}
    ]
  }
]
```

Preencha as opções de ângulo de verdade com base na pesquisa do tema. Não use texto de placeholder nas descrições dos ângulos.

## Passo 3. Escrever o rascunho

Escreva o post seguindo estas regras:
- Leia o voice.md pra pegar tom, ritmo, estilo de gancho, estilo de chamada pra ação e a seção de padrões de ausência (o que aquela voz nunca faz)
- Leia o about-me.md pra pegar o público e o contexto do tema
- Espelhe o tamanho das frases e o ritmo dos parágrafos do voice.md
- Evite toda palavra, estrutura e padrão banido na seção de ausência do voice.md
- Use o padrão de gancho que combina com o ângulo escolhido
- Termine com o estilo de chamada pra ação do voice.md

Entregue o post dentro de um bloco de código simples:

```
[O post completo vai aqui com todas as quebras de linha e a formatação exatamente como deve aparecer na rede social]
```

Depois do bloco de código, acrescente de 2 a 3 frases explicando por que você escolheu esse gancho e essa estrutura, citando padrões específicos do voice.md.

## Passo 4. Iterar

Pergunte ao dono:

> Como ficou? Me diz o que mudar, ou fala "pode mandar" que eu salvo a versão final.

Se o dono der um feedback, revise e entregue um novo bloco de código. No máximo 3 rodadas de revisão.

Se o dono falar "pode mandar" ou algo equivalente, salve o post final como um arquivo markdown no projeto.

Depois diga:

> Post salvo.

## Regras

- Sempre leia o about-me.md e o voice.md antes de escrever.
- Sempre entregue os posts dentro de um bloco de código simples.
- Nunca use travessões em nenhum post.
- Escreva sempre em português do Brasil, a menos que o voice.md diga outra coisa.
- Não adicione hashtags a menos que o voice.md use hashtags explicitamente.
- Não adicione chamadas pra ação de caça-engajamento a menos que elas apareçam no voice.md.
- Mantenha os posts entre 150 e 300 palavras, a menos que o dono peça outra coisa.
- Planeje antes de escrever. Nunca pule o Passo 2.
