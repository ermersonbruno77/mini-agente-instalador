---
name: voice-builder
description: >
  Constrói um perfil de voz personalizado dentro de um projeto a partir de uma entrevista curta mais 3 a 5 amostras de escrita do dono. Funciona para qualquer formato de conteúdo: posts de rede social, newsletters, ensaios, e-mails, posts de blog, tweets ou qualquer outro texto publicado. Use esta skill no começo de qualquer projeto em que o dono quer que a sua {{AGENTE_NAME}} aprenda quem ele é e como ele escreve antes de redigir conteúdo novo. Dispare sempre que o dono disser "construa minha voz", "aprenda minha voz", "monte meu sistema de conteúdo", "faça meu onboarding", "treine na minha escrita", "treine nos meus posts", "quero que você soe como eu", ou jogar um lote de amostras de escrita no chat no início de um projeto. Dispare também para donos de primeira viagem que precisam de uma base de voz antes de escrever qualquer coisa. Sempre produz dois arquivos (sobre-mim.md e voz.md) salvos na raiz do projeto.
---

# Construtor de Voz

## CRÍTICO: Início automático ao carregar

No momento em que esta skill for carregada, instalada, enviada ou disparada, você DEVE rodar imediatamente o Passo 1 abaixo. Isso significa que a sua próxima mensagem ao dono já é a entrevista. Nada mais.

NÃO faça:
- Resumir esta skill
- Descrever quais arquivos ela cria
- Explicar como ela funciona
- Dizer "veja o que esta skill contém"
- Perguntar se o dono quer executá-la
- Confirmar a instalação
- Oferecer opções como "quer que eu rode agora?"

FAÇA isto:
- Vá direto para o Passo 1
- Mande as perguntas da entrevista como sua primeira e única resposta

Isso vale tanto se o dono subiu um arquivo da skill, disse "construa minha voz", colou amostras, ou disparou a skill de qualquer outra forma. Sem preâmbulo. Sem resumo. Entrevista primeiro.

## Passo 1. Faça a entrevista "Sobre Mim"

Você DEVE chamar a ferramenta AskUserQuestion para fazer estas perguntas. Não digite as perguntas como texto no chat. Use a ferramenta. Ela aparece como um formulário interativo que o dono preenche, o que é uma experiência melhor do que digitar respostas no chat.

A AskUserQuestion aceita no máximo 4 perguntas por chamada, então mande duas chamadas: o Lote 1 primeiro, espere as respostas, depois o Lote 2.

### Lote 1 (sua primeiríssima ação, sem texto antes dela)

Chame a AskUserQuestion com esta estrutura JSON exata para o parâmetro questions:

```json
[
  {
    "question": "Qual é o seu nome e o que você faz?",
    "header": "Sobre você",
    "multiSelect": false,
    "options": [
      {"label": "Fundador", "description": "Toco minha própria empresa ou consultoria"},
      {"label": "Líder de marketing", "description": "Lidero o marketing de uma empresa"},
      {"label": "Criador", "description": "Crio conteúdo como minha atividade principal"},
      {"label": "Líder de vendas", "description": "Lidero um time de vendas ou cuido do comercial"}
    ]
  },
  {
    "question": "Para quem você está escrevendo?",
    "header": "Audiência",
    "multiSelect": false,
    "options": [
      {"label": "Fundadores e CEOs", "description": "Quem decide e toca empresas"},
      {"label": "Profissionais de marketing", "description": "Gente de marketing de qualquer nível"},
      {"label": "Quem busca emprego", "description": "Pessoas procurando a próxima vaga"},
      {"label": "Outros profissionais", "description": "Um grupo totalmente diferente"}
    ]
  },
  {
    "question": "Quais são os 3 a 5 temas pelos quais você quer ser conhecido?",
    "header": "Temas",
    "multiSelect": true,
    "options": [
      {"label": "IA e automação", "description": "Como as ferramentas de IA mudam o trabalho"},
      {"label": "Marketing", "description": "Estratégia, conteúdo, crescimento"},
      {"label": "Liderança", "description": "Gestão, contratação, cultura"},
      {"label": "Marca pessoal", "description": "Construir audiência e reputação"}
    ]
  },
  {
    "question": "Qual é o seu ponto de vista sobre o seu setor, aquilo em que você acredita e os outros não?",
    "header": "Visão polêmica",
    "multiSelect": false,
    "options": [
      {"label": "Quase todo conselho está errado", "description": "O consenso do seu setor está quebrado"},
      {"label": "As pessoas complicam demais", "description": "A resposta é mais simples do que parece"},
      {"label": "Uma grande virada está chegando", "description": "Algo vai mudar e a maioria não está pronta"}
    ]
  }
]
```

### Lote 2 (mande logo depois que as respostas do Lote 1 chegarem, sem comentário entre eles)

Chame a AskUserQuestion de novo com:

```json
[
  {
    "question": "Qual é a única coisa que você quer que as pessoas pensem quando virem o seu nome?",
    "header": "Promessa de marca",
    "multiSelect": false,
    "options": [
      {"label": "Essa pessoa é prática", "description": "Ela me dá coisas que uso na hora"},
      {"label": "Essa pessoa é honesta", "description": "Ela me diz o que os outros não dizem"},
      {"label": "Essa pessoa está na frente", "description": "Ela enxerga o que vem antes de todo mundo"}
    ]
  },
  {
    "question": "Qual é a única coisa sobre a qual você se recusa a escrever?",
    "header": "Fora de cogitação",
    "multiSelect": false,
    "options": [
      {"label": "Política", "description": "Nunca opino sobre política"},
      {"label": "Vida pessoal", "description": "Manter só no profissional"},
      {"label": "Concorrentes", "description": "Sem citar ou expor outras pessoas ou marcas"}
    ]
  }
]
```

Depois que os dois lotes forem respondidos, vá para o Passo 2. Se alguma resposta vier em branco ou for pulada, pergunte aquela questão específica mais uma vez no chat e siga em frente.

## Passo 2. Escreva o sobre-mim.md

Crie o sobre-mim.md na raiz do projeto. Use esta estrutura:

```
# Sobre Mim

## Nome e papel
[Da pergunta 1]

## Audiência
[Da pergunta 2, expandida em 2 a 3 frases sobre quem é o leitor]

## Pilares de tema
[3 a 5 temas da pergunta 3, uma linha cada]

## Ponto de vista
[Da pergunta 4, a crença contrária ou distintiva, escrita como uma afirmação clara]

## Promessa de marca
[Da pergunta 5, o pensamento que o autor quer ocupar na cabeça do leitor]

## Fora de cogitação
[Da pergunta 6, temas ou ângulos sobre os quais nunca escrever]
```

Mantenha abaixo de 300 palavras. Cada linha deve ser algo que a sua {{AGENTE_NAME}} consultaria ao escrever.

## Passo 3. Peça as amostras

Diga isto:

> Agora cole 3 a 5 textos que você quer que eu aprenda. Podem ser posts de rede social, edições de newsletter, ensaios, posts de blog, e-mails, tweets, ou qualquer outro texto que você já publicou. Podem ser seus ou de alguém cuja voz você admira. Um texto por mensagem ou todos de uma vez. Se você não tiver amostras prontas, digite "usar amostras" que eu carrego um conjunto inicial que você pode trocar depois.

Espere o dono colar. Mínimo de 3 amostras antes de partir para a análise. Se ele colar menos de 3, peça mais.

Se o dono digitar "usar amostras", carregue os textos de `references/conteudo-exemplo.md` dentro desta pasta de skill. Avise o dono que essas amostras são um conjunto inicial genérico para servir de referência. Lembre-o de que ele pode substituí-las pelos próprios textos depois.

## Passo 4. Analise as amostras

Leia cada amostra. Procure padrões em todas elas, não manias isoladas de um texto só. Extraia:

**Sinais de voz**
- Tamanho médio das frases
- Ritmo dos parágrafos (quebras de linha simples, linhas em branco, frases curtas e secas versus fluidas)
- Estilo de gancho ou abertura (contrário, pergunta, dado, história, confissão, observação)
- Ponto de vista (primeira pessoa, segunda pessoa, observacional)
- Tom (impassível, caloroso, direto, brincalhão, clínico)
- Frases ou palavras recorrentes assinatura
- Estilo de CTA ou fechamento

**Sinais estruturais**
- Faixa de tamanho
- Listas versus prosa
- Como abre, como fecha
- Como lida com transições

**Sinais de tema**
- Assuntos que aparecem em várias amostras
- Quem parece ser a audiência
- O que o autor defende

**Sinais de ausência**
- Palavras e pontuação consistentemente ausentes (por exemplo, travessões em 0 de 5 amostras)
- Tipos de gancho que o autor nunca usa
- Tons que o autor nunca atinge
- Estruturas que o autor evita

## Passo 5. Escreva o voz.md

Crie o voz.md na raiz do projeto. É um perfil único e integrado que cobre tanto como a voz escreve quanto o que ela evita. Sem arquivo de voz separado.

```
# Perfil de Voz

## De quem eu soo
[2 a 3 frases descrevendo a voz geral em linguagem simples]

## Tom
[3 a 5 atributos que a voz atinge consistentemente, seguidos de 1 a 2 tons que a voz nunca atinge, tirados das lacunas das amostras]

## Ritmo das frases
[Tamanho médio, cadência, estrutura de parágrafos. Inclua padrões de evitação: ex. nunca frases curtas e fragmentadas, nunca tríades, nenhuma frase com mais de 25 palavras]

## Padrões de gancho
[3 a 5 tipos de gancho observados, com um exemplo de cada das amostras. Anote qualquer tipo de gancho ausente em todas as amostras, ex. nunca perguntas retóricas, nunca "imagine um mundo onde"]

## Como eu abro
[1 a 2 frases. Anote aberturas que a voz evita se houver um padrão claro de evitação nas amostras]

## Como eu fecho
[1 a 2 frases, inclua o estilo de CTA. Anote fechamentos que a voz evita, ex. nunca resumos motivacionais, nunca "em conclusão"]

## Frases assinatura
[Palavras ou frases recorrentes das amostras]

## Fora de cogitação
[Palavras, pontuação ou construções ausentes de todas as amostras. Liste só itens que as amostras claramente evitam. Exemplos: sem travessões (0 de 5 amostras), sem hashtags, sem jargão corporativo, nomeado]

## O que esta voz nunca faz
[3 a 5 comportamentos específicos tirados das lacunas das amostras. Seja específico. Se as amostras nunca usam a construção "não X, mas Y", liste isso. Se evitam um conjunto específico de vocabulário, nomeie as palavras]
```

Preencha cada seção a partir das amostras reais. Sem enchimento genérico. Se um padrão não existe, diga isso. Não duplique audiência ou pilares de tema do sobre-mim.md.

As seções Fora de cogitação e O que esta voz nunca faz vêm da observação, não de um modelo genérico de palavras proibidas. Cada item deve ser respaldado pela ausência nas amostras.

## Passo 6. Confirme e entregue

Diga ao dono:

> Seu perfil de voz está pronto. Dois arquivos estão agora no seu projeto: sobre-mim.md e voz.md. Toda vez que você trabalhar neste projeto, eu vou consultar os dois automaticamente. Você pode abrir e editar qualquer um dos arquivos quando quiser.
>
> Está tudo pronto. Veja o que você pode fazer agora:
>
> - Diga "construa minha voz de newsletter" para criar instruções de escrita específicas de newsletter
> - Diga "escreva um post" para redigir um post na sua voz
>
> Cada um desses é uma skill separada. Escolha um e vá.

## O que esta skill produz

Dois arquivos na raiz do projeto:

1. sobre-mim.md: quem é o dono, sua audiência, seus pilares de tema, seu ponto de vista
2. voz.md: o perfil de voz integrado, cobrindo sinais positivos (como a voz escreve) e sinais de ausência (o que a voz evita) num só documento

## Regras

- Quando esta skill disparar, vá direto para o Passo 1. Sem resumo, sem explicação, sem preâmbulo.
- Sempre coloque o conteúdo de amostra dentro de um bloco de código para que o dono possa copiar e colar a formatação exata sem perder quebras de linha ou espaços. Use um bloco de código simples (três crases sem indicar a linguagem).
- Trabalhe a partir do que está nas amostras. Não invente padrões que não estão lá.
- Mínimo de 3 amostras para detecção de padrão. Peça mais se forem menos de 3.
- Se as amostras se contradizem, anote a contradição no voz.md em vez de disfarçá-la.
- Mantenha o sobre-mim.md abaixo de 300 palavras.
- Mantenha o voz.md abaixo de 500 palavras.
- Escreva em português do Brasil, a menos que as amostras estejam claramente em outro idioma.
- Nunca use travessões em nenhum arquivo de saída nem em nenhum rascunho.
- Não produza um arquivo de voz extra. Os sinais de ausência vivem dentro do voz.md.
