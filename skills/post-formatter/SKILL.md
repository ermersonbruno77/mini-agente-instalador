---
name: post-formatter
description: >
  Transforma um tema num post pronto pra publicar na rede social usando os frameworks PAS, AIDA, BAB, STAR ou SLAY. De 200 a 250 palavras, no máximo 20 linhas, formatado pra leitura no celular com linha em branco entre as frases. Use esta skill sempre que o dono pedir "formata isso como post", "transforma isso num post pra rede social", "escreve em PAS" ou qualquer framework pelo nome, ou quando ele quiser um post bem estruturado a partir de um tema. Diferente da post-writer: a post-formatter aplica um framework rígido. A post-writer escreve na voz do dono, sem amarras de framework.
---

# Post Formatter

## IMPORTANTE: começar sozinha ao carregar

Quando esta skill for acionada, vá direto pro Passo 1. Não resuma a skill. Comece a coletar as informações na hora.

## Passo 1. Coletar as informações

Chame a AskUserQuestion:

```json
[
  {
    "question": "Sobre qual tema você quer postar?",
    "header": "Tema",
    "multiSelect": false,
    "options": [
      {"label": "Vou digitar o tema", "description": "Uma frase descrevendo o assunto"},
      {"label": "Colar um monte de contexto", "description": "Anotações, números, transcrições pra virar um post"}
    ]
  },
  {
    "question": "Qual framework?",
    "header": "Framework",
    "multiSelect": false,
    "options": [
      {"label": "PAS", "description": "Problema, Agitação, Solução"},
      {"label": "AIDA", "description": "Atenção, Interesse, Desejo, Ação"},
      {"label": "BAB", "description": "Antes, Depois, Ponte"},
      {"label": "STAR", "description": "Situação, Tarefa, Ação, Resultado"},
      {"label": "SLAY", "description": "História, Lição, Conselho prático, Você"},
      {"label": "Escolha por mim", "description": "Recomende o melhor framework com base no tema"}
    ]
  }
]
```

Faça uma pergunta de acompanhamento:

> Tem mais alguma coisa que eu deva saber? Fatos, números, observações de tom, ou pra quem é isso.

Espere a resposta.

## Passo 2. Escrever o post

Aplique estas regras gerais a toda saída:

- No máximo 20 linhas, total de 200 a 250 palavras (~1.200 caracteres)
- Linha em branco depois de cada linha
- Na maioria das linhas: uma frase, 55 caracteres ou menos
- Até 4 linhas podem ser mini-parágrafos (2 a 3 frases, 110 caracteres ou menos)
- Palavras simples, nível fácil de leitura. Zero advérbios, zero jargão, zero enrolação
- Sem travessões
- Sem perguntas, a menos que o próprio gancho seja uma pergunta
- Sem emojis, exceto o sinal de check pra listas numeradas (1. 2. 3.) e o símbolo de reciclagem no CTA
- Regra de Três: no máximo dois trios por post
- Varie o começo das frases. Não abuse do "Eu"

## Passo 3. Estrutura

- **Linha 1 (Gancho)**: Em negrito. 50 caracteres ou menos.
- **Linha 2 (Virada / Contraste)**: 50 caracteres ou menos. Contraria ou surpreende o gancho.
- **Linhas 3 a 18 (Núcleo)**: O framework escolhido, dividido em 3 a 5 linhas por etapa. Qualquer lista dentro de uma etapa tem que ter exatamente três itens (1. 2. 3.). Use setas pra mostrar o fluxo onde fizer sentido.

Mapas dos frameworks:

- **PAS**: Problema -> Agitação -> Solução
- **AIDA**: Atenção -> Interesse -> Desejo -> Ação
- **BAB**: Antes -> Depois -> Ponte
- **STAR**: Situação -> Tarefa -> Ação -> Resultado
- **SLAY**: História -> Lição -> Conselho prático -> Você

- **Linhas 19 a 20 (Fechamento e CTA)**: 2 a 3 linhas que cravam a lição. Feche com uma destas frases seguida do símbolo de reciclagem: "Reposta se", "Reposta isso", ou "Se isso ajudou, reposta".

## Passo 4. Saída

Entregue o post finalizado dentro de um bloco de código. Sem introdução, sem comentários no fim.

## Regras

- Devolva só o post finalizado. Sem meta-comentário.
- Faça valer os limites de tamanho de linha, contagem de palavras e contagem de linhas. Conte de fato.
- Nunca use travessões.
- Escreva sempre em português do Brasil, a menos que voice.md diga outra coisa.
- Se o dono tiver voice.md no projeto, ajuste o tom e o ritmo pra combinar com ele.
- Se usar um trio, ele tem exatamente três itens. Nem dois, nem quatro.
