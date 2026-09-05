---
name: content-matrix
description: >
  Gera mais de 32 ideias de posts pra rede social numa única tabela, cruzando os pilares de conteúdo do dono com 8 formatos de conteúdo comprovados. Use esta skill sempre que o dono pedir "me dá ideias de post", "matriz de conteúdo", "sobre o que eu deveria postar", "gera ideias de post", "ideação de conteúdo" ou "monta meu conteúdo do mês". Puxa de about-me.md e voice.md se eles existirem, senão pergunta os pilares e o contexto.
---

# Matriz de Conteúdo

## CRÍTICO: começar sozinha ao carregar

No instante em que esta skill dispara, vá direto pro Passo 1. Não resuma a skill. Não explique o que ela faz. Comece a coletar as informações imediatamente.

## Passo 1. Coletar as informações

Cheque se o projeto tem o arquivo about-me.md. Se ele existir, leia e já preencha a descrição de quem é o dono. Pule essa pergunta e conte pro dono o que você puxou.

Se o about-me.md não existir, pergunte:

> Me passa pelo menos dois parágrafos descrevendo quem você é, o que você faz e sobre o que gosta de falar. Quanto mais específico você for, mais relevantes ficam as ideias.

Espere a resposta.

Depois chame o AskUserQuestion:

```json
[
  {
    "question": "Quais são seus pilares de conteúdo?",
    "header": "Pilares",
    "multiSelect": false,
    "options": [
      {"label": "Eu vou digitar", "description": "Tenho de 3 a 4 pilares de conteúdo pra usar"},
      {"label": "Puxa do voice.md", "description": "Usa os temas que já estão definidos nos meus arquivos de voz"},
      {"label": "Sugere pra mim", "description": "Com base no meu about-me.md, recomenda 4 pilares"}
    ]
  }
]
```

Se o dono digitar os próprios, aceite de 3 a 5 pilares. Se forem menos de 3, peça mais.

Se o dono escolher "Sugere pra mim", leia o about-me.md, proponha 4 pilares que cubram o posicionamento dele e peça pra ele confirmar ou ajustar antes de continuar.

## Passo 2. Montar a matriz

Gere uma tabela em markdown com:

- Eixo X (colunas): 8 formatos de conteúdo, sempre nesta ordem:
  1. Acionável
  2. Motivacional
  3. Analítico
  4. Contrário
  5. Observação
  6. X vs Y
  7. Presente vs Futuro
  8. Lista
- Eixo Y (linhas): os 3 a 5 pilares do dono

Cada célula contém uma ideia de post específica e concreta, feita sob medida pra aquele pilar e aquele formato. Nada genérico. Nada que sirva igual em vários pilares.

Definições de formato pra aplicar ao preencher cada célula:

- **Acionável**: Um passo a passo ultra específico. Ensina o leitor a fazer uma coisa.
- **Motivacional**: História inspiradora sobre alguém que fez algo extraordinário no nicho.
- **Analítico**: Destrincha por que algo funciona do jeito que funciona.
- **Contrário**: Vai contra o conselho comum do nicho e sustenta o ponto.
- **Observação**: Uma tendência escondida, silenciosa ou pouco comentada que o dono notou.
- **X vs Y**: Compara duas coisas (ferramentas, estilos, métodos, empresas).
- **Presente vs Futuro**: O estado atual versus uma previsão específica, com o porquê.
- **Lista**: Uma lista de recursos, dicas, erros, lições ou passos.

A ideia de cada célula tem que ser uma manchete específica, não um tema. Bom: "A fórmula de gancho de 3 linhas que mudou meus posts". Ruim: "Ganchos".

## Passo 3. Entregar (de acordo com a superfície)

Escolha o modo de saída de acordo com a superfície onde você está rodando. Não jogue a tabela dentro de um bloco de código markdown, porque isso renderiza como texto monoespaçado e deixa uma grade de 5×8 difícil de ler.

- **Claude.ai ou Claude Cowork (superfícies de chat com suporte a gráfico interativo):** renderize a matriz como um gráfico interativo ou widget de tabela interativa. Pilares nas linhas, formatos nas colunas, cada célula com uma manchete específica. O dono deve conseguir clicar numa célula pra ver a manchete completa e qualquer nota de expansão. Não jogue também a tabela em markdown, porque o gráfico é a entrega.
- **Claude Code (superfície com sistema de arquivos, tem ferramentas Write/Edit):** salve a matriz em `content-matrix-YYYY-MM-DD.md` na pasta de trabalho atual e imprima a mesma tabela inline na resposta como tabela markdown simples (sem envolver em três crases). Confirme o caminho do arquivo pra o dono conseguir abrir.
- **Alternativa (sem gráfico interativo, sem ferramentas de sistema de arquivos):** entregue uma tabela markdown simples inline. Ainda sem envolver em bloco de código.

Abaixo da tabela ou do gráfico, acrescente uma frase apontando a ideia mais forte de toda a matriz e o porquê.

## Passo 4. Oferecer o próximo passo

Pergunte:

> Tem alguma célula aqui que você quer que eu escreva como post completo? Cita a célula pelo pilar + formato (por exemplo "Ganchos × Contrário") que eu passo pra skill post-writer ou post-formatter.

No Claude Code, ofereça também acrescentar o post escrito no mesmo arquivo `content-matrix-YYYY-MM-DD.md`, embaixo da referência da célula.

## Regras

- Mínimo de 3 pilares, máximo de 5. Mais que 5 dilui a matriz.
- Toda ideia de célula tem que ser específica pra aquele pilar E aquele formato. Não reutilize a mesma ideia em pilares diferentes.
- Ajuste a linguagem à voz do dono se o voice.md existir.
- Escreva sempre em português do Brasil, a menos que o voice.md diga outra coisa.
- Nunca use travessões.
