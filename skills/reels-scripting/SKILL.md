---
name: reels-scripting
description: >
  Transforma um Instagram Reel de referência num roteiro pro seu próprio Reel, afinado pra sua voz e reaproveitado a partir do seu conteúdo. Recebe a URL de um Reel ou um link de referência das suas anotações, usa uma ferramenta de coleta de posts pra baixar o vídeo, manda pro Gemini 2.5 Flash pra análise completa de transcrição, gancho e estrutura, e depois escreve um roteiro novo aplicando os mesmos padrões ao seu tema. Use essa skill sempre que o dono disser "faz o roteiro de um reel", "roteiro de reels", "transforma isso num reel", colar a URL de um Instagram Reel ou citar a base de reels de referência dele. Requer as variáveis de ambiente APIFY_API_TOKEN e GOOGLE_AI_API_KEY.
---

# Roteiro de Reels

## IMPORTANTE: começar sozinha ao carregar

Quando essa skill disparar, vá direto pro Passo 1. Não resuma.

## Pré-requisitos

Essa skill precisa de:

- Variável de ambiente `APIFY_API_TOKEN` (coleta de posts do Instagram)
- Variável de ambiente `GOOGLE_AI_API_KEY` (análise de vídeo pelo Gemini 2.5 Flash)
- Node.js 18+ e os pacotes `apify-client` e `@google/generative-ai`

Se faltar alguma variável de ambiente, diga pro dono rodar:

```
! export APIFY_API_TOKEN=seu_token
! export GOOGLE_AI_API_KEY=sua_chave
```

Depois pare até as duas estarem definidas.

## Passo 1. Pegar a referência

Pergunte:

> Cola a URL do Reel de referência ou o link das suas anotações. É o Reel fora da curva de que você quer fazer a engenharia reversa do formato.

Espere a URL.

Se o dono colar um link das anotações dele, siga o link via WebFetch, localize a URL do Instagram Reel na página e extraia. Se nenhuma URL de Reel for encontrada na página, peça pro dono colar a URL do Reel direto.

## Passo 2. Pegar o tema

Pergunte:

> Qual é o tema que você quer reaproveitar pra esse Reel? Cola o trecho relevante do seu conteúdo, ou escreve a ideia central em uma frase.

Espere o tema. Leia os arquivos de voz e de contexto do dono do projeto, se existirem, pra que o roteiro combine com a voz dele.

## Passo 3. Coletar e baixar o Reel

Crie `~/Desktop/Reels/` se ainda não existir. Escreva um script Node.js em `~/Desktop/Reels/analyse-reel.js` que:

1. Use o `apify-client` pra chamar `apify/instagram-reel-scraper` com `{ directUrls: [reelUrl], resultsLimit: 1 }`. Se isso não retornar itens, caia pra `{ urls: [reelUrl], resultsLimit: 1 }`, e depois pra `apify/instagram-scraper` com `{ directUrls: [reelUrl], resultsType: 'posts', resultsLimit: 1 }`.
2. Extraia `videoUrl` do item retornado.
3. Baixe o vídeo pra `~/Desktop/Reels/downloads/{username}_{shortCode}.mp4`.
4. Salve os dados brutos da coleta em `~/Desktop/Reels/reel_data_{shortCode}.json`.

Rode o script. Confirme o tamanho do arquivo e os metadados (visualizações, curtidas, comentários, primeiros 200 caracteres da legenda) antes de continuar.

## Passo 4. Analisar com o Gemini 2.5 Flash

Estenda o script Node (ou rode uma segunda passada) que:

1. Leia o `.mp4` baixado como base64.
2. Chame `genAI.getGenerativeModel({ model: 'gemini-2.5-flash' })`.
3. Envie o vídeo com este prompt exato:

```
Estou estudando este Reel pra escrever meu próprio roteiro num estilo parecido pro meu público de [PÚBLICO DO ARQUIVO DE CONTEXTO].

## Transcrição completa
- Transcreva CADA palavra com timestamps

## Gancho
- Primeiras palavras ditas, exatas
- Contagem de palavras do gancho
- O que faz parar o scroll?

## Padrões de linguagem
- Comprimento médio das frases
- Proporção de você/seu vs eu/meu
- Transições entre os pontos
- Onde estão os minimizadores (tipo "só")?

## Estrutura
- Duração total
- Quebra por seções com os tempos
- Qual é o momento de antes/depois?
- Qual é o CTA?

## Uma sacada-chave
- A única técnica mais importante pra aprender deste Reel
```

Salve a análise em `~/Desktop/Reels/analysis_reference_{shortCode}.md`.

## Passo 5. Escrever o novo roteiro do Reel

Usando a análise do Passo 4, o tema do Passo 2 e os arquivos de voz do dono, escreva um roteiro novo de Reel em `~/Desktop/Reels/reel-[slug].md`.

Aplique estas regras (inegociáveis):

### Gancho
- Nunca abra com "Eu". Use "isto", "você", um fato ou um nome.
- Formatos comprovados: "Isto mudou... pra sempre" / virada negativa ("X é inútil, a não ser que...") / declaração de capacidade.
- O gancho cria curiosidade ou quebra de padrão em 3 segundos.
- Espelhe a contagem de palavras e a estrutura do gancho da análise da referência.

### Corpo
- PT-BR. Frases curtas. Sem travessões, sem ponto e vírgula.
- Use "você" e "só" de forma conversacional ("você só joga ali...").
- Nunca junte três ou mais fragmentos picados. Combine numa frase fluida.
- Nunca diga a conclusão. Deixe os fatos falarem.
- Sem "link na bio". Use automação por comentário.

### Gatilho de comentário
- Só uma palavra em maiúsculas (ROTEIRO, GUIA, PROMPTS, VÍDEO).
- Precisa se relacionar direto com o que está sendo prometido.
- Sem aspas, sem "abaixo", sem pontuação no final.

### CTA
- "Comenta [PALAVRA] e eu te mando [coisa específica]"
- Curto. Sem encheção tipo "o link do meu material completo".

### Duração e estrutura
- Mire de 30 a 45 segundos no total.
- No máximo 2 pontos-chave, não 3.
- A legenda espelha o roteiro. Atualize os dois juntos.

### Estrutura do arquivo de roteiro

```
# Reel: [título]

## Análise da referência
- URL: [url do reel]
- Visualizações: [número]
- Técnica-chave: [da análise do Gemini]

## Duração-alvo
30-45 segundos

## Gancho (0-3s)
[Palavras exatas]

## Ponto 1 ([início]-[fim]s)
[Palavras exatas]

## Ponto 2 ([início]-[fim]s)
[Palavras exatas]

## CTA ([início]-[fim]s)
[Palavras exatas incluindo "Comenta [PALAVRA]"]

---

## Legenda
[Espelha o roteiro, formatado pro Instagram]

## Gatilho de comentário
[PALAVRA]

## Entregável
[O que o gatilho de comentário libera]

---

## Notas visuais
[Cortes, ideias de b-roll, textos na tela]
```

## Passo 6. Loop de QA

Pontue o roteiro contra as regras do Passo 5. Toda violação precisa ser corrigida. Repontue até o roteiro bater 95/100. Nunca mostre nada abaixo de 95 pro dono.

Violações comuns pra checar:
- Abre com "Eu"
- Fragmentos picados de três ou mais
- Diz a conclusão
- Gatilho de comentário com várias palavras ou estilizado
- Duração acima de 45 segundos lido em voz alta
- 3 pontos em vez de 2
- A legenda não espelha o roteiro

## Passo 7. Oferecer o pipeline

Depois do roteiro aprovado, ofereça:

> Dois caminhos daqui:
>
> 1. Grava você mesmo.
> 2. Gera automático com voz por IA + avatar por IA + motion graphics. Se você tiver o projeto de vídeo configurado, roda o pipeline com a config deste roteiro.

## Regras

- Nunca pule o portão de QA 95/100.
- Sempre leia os arquivos de voz e de contexto antes de escrever. Combinar com a voz é inegociável.
- Nunca invente métricas do Reel de referência. Use só o que a ferramenta de coleta retornar.
- PT-BR. Sem travessões. Sem ponto e vírgula.
- Todo roteiro entregue inclui a legenda exata e o gatilho de comentário junto com o roteiro. Nunca entregue só o roteiro.
- Se a coleta do Reel de referência falhar nas três variantes, relate a falha e pare. Não invente a análise.
- O modelo é o Gemini 2.5 Flash. Não substitua sem a aprovação do dono.
