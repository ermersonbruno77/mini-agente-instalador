---
name: hook-generator
description: >
  Gera 6 variações de ganchos (hooks) no estilo clickbait para qualquer assunto. Ganchos de duas linhas montados na fórmula: uma linha de abertura com até 40 caracteres e uma linha de contraste forte com até 40 caracteres. Inclui números, frases em primeira pessoa ("Como eu" ou "Eu") e métricas. Use esta skill sempre que o dono pedir "escreve uns ganchos", "ideias de hook", "gera ganchos", "preciso de um gancho pra um post sobre...", ou colar um assunto e pedir aberturas de post. Saída rápida, sem enrolação.
---

# Gerador de Ganchos

## CRÍTICO: Começar sozinha ao carregar

Quando esta skill for acionada, vá direto pro Passo 1. Não resuma. Não fique explicando o que faz um bom gancho.

## Passo 1. Pegar o assunto

Se o dono já colou um assunto na mensagem dele, use esse assunto e pule pro Passo 2.

Caso contrário, pergunte:

> Sobre qual assunto você quer os ganchos?

Espere a resposta.

## Passo 2. Escrever 6 variações de gancho

Todo gancho tem a mesma estrutura:

- **Linha 1 (Abertura)**: no máximo 40 caracteres. Sem perguntas. Afirma algo inesperado, específico ou de impacto.
- **Linha 2 (Contraste)**: no máximo 40 caracteres. Contradiz, ressignifica ou derruba a abertura.

Toda variação precisa:

- Incluir pelo menos uma frase em primeira pessoa ("Como eu" ou "Eu") ao longo das duas linhas
- Incluir um número ou métrica sempre que der
- Seguir os princípios do clickbait: tensão, lacuna de curiosidade, algo em jogo

Produza 6 variações cobrindo ângulos diferentes:

1. **Puxada por número**: comece com um número ou métrica específica
2. **Contrária**: declare uma crença e depois vire ela do avesso
3. **Transformação pessoal**: antes versus depois com um número
4. **Empréstimo de autoridade**: cite um nome, ferramenta ou marca
5. **Confissão**: assuma um erro ou uma perda
6. **Choque de futuro**: uma previsão ou "X está prestes a mudar"

## Passo 3. Formato de saída

```
GANCHOS para [assunto]

1. [Puxada por número]
[Linha 1]
[Linha 2]

2. [Contrária]
[Linha 1]
[Linha 2]

3. [Transformação pessoal]
[Linha 1]
[Linha 2]

4. [Empréstimo de autoridade]
[Linha 1]
[Linha 2]

5. [Confissão]
[Linha 1]
[Linha 2]

6. [Choque de futuro]
[Linha 1]
[Linha 2]
```

## Passo 4. Oferecer o próximo passo

Pergunte:

> Quer que eu transforme um desses num post completo? Chame a skill post-formatter passando o número do gancho.

## Regras

- No máximo 40 caracteres por linha. Conte os caracteres.
- Sem perguntas na linha de abertura.
- Sem travessões.
- Sem palavras de enchimento. Cada palavra tem que justificar o lugar dela.
- Prefira números em algarismo a números por extenso (3, não três).
- Português do Brasil, a não ser que o arquivo voice.md diga outra coisa.
- Nunca amenize. Um gancho fraco é pior que nenhum gancho.
