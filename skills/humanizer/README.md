# Humanizer

Uma skill que remove os sinais de escrita gerada por IA de um texto, deixando ele mais natural e humano.

## Instalação

Copie a pasta da skill pro diretório de skills da sua {{AGENTE_NAME}}. Não há etapa de build: a skill é só o `SKILL.md`.

## Uso

```
/humanizer

[cole seu texto aqui]
```

Ou peça pra sua {{AGENTE_NAME}} humanizar o texto direto:

```
Humaniza esse texto pra mim: [seu texto]
```

### Calibragem de voz

Pra casar com o seu estilo de escrita, forneça uma amostra da sua própria escrita:

```
/humanizer

Aqui vai uma amostra da minha escrita pra calibrar a voz:
[cole 2 ou 3 parágrafos da sua própria escrita]

Agora humaniza esse texto:
[cole o texto de IA pra humanizar]
```

A skill analisa o ritmo das suas frases, suas escolhas de palavra e seus vícios, depois aplica isso na reescrita em vez de produzir uma saída genérica e "limpa".

## Visão geral

Baseada no guia público "sinais de escrita por IA", mantido por um projeto colaborativo de limpeza de conteúdo gerado por IA numa enciclopédia aberta. Esse guia vem da observação de milhares de casos de texto gerado por IA.

A skill também inclui uma passada final de auditoria do tipo "isso está obviamente gerado por IA" e uma segunda reescrita, pra pegar os vícios de IA que sobraram no primeiro rascunho.

### Insight central do guia

> "Os modelos de linguagem usam algoritmos estatísticos pra adivinhar o que deve vir a seguir. O resultado tende ao desfecho estatisticamente mais provável que se aplica à maior variedade de casos."

## 33 Padrões Detectados (com exemplos de Antes/Depois)

### Padrões de Conteúdo

| # | Padrão | Antes | Depois |
|---|---------|--------|--------|
| 1 | **Inflar a importância** | "marcando um momento decisivo na evolução de..." | "foi criado em 1989 pra coletar estatísticas regionais" |
| 2 | **Citar nomes de notoriedade** | "citada na NYT, BBC, FT e The Hindu" | "Numa entrevista à NYT em 2024, ela defendeu..." |
| 3 | **Análises superficiais com gerúndio** | "simbolizando... refletindo... evidenciando..." | Remova ou desenvolva com fontes reais |
| 4 | **Linguagem promocional** | "aninhada na deslumbrante região" | "é uma cidade na região de Gonder" |
| 5 | **Atribuições vagas** | "Especialistas acreditam que tem papel crucial" | "segundo um levantamento de 2019 de..." |
| 6 | **Desafios formulaicos** | "Apesar dos desafios... continua a prosperar" | Fatos específicos sobre os desafios reais |

### Padrões de Linguagem

| # | Padrão | Antes | Depois |
|---|---------|--------|--------|
| 7 | **Vocabulário de IA** | "Na verdade... além disso... testemunho... cenário... evidenciando" | "também... continuam comuns" |
| 8 | **Fuga do verbo ser** | "serve como... apresenta... ostenta" | "é... tem" |
| 9 | **Paralelismos negativos / negações no rabo** | "Não é só X, é Y", "..., sem chute" | Diga o ponto direto |
| 10 | **Regra de três** | "inovação, inspiração e insights" | Use o número natural de itens |
| 11 | **Troca de sinônimos** | "protagonista... personagem principal... figura central... herói" | "protagonista" (repita quando for mais claro) |
| 12 | **Faixas falsas** | "do Big Bang à matéria escura" | Liste os temas direto |
| 13 | **Voz passiva / fragmentos sem sujeito** | "Nenhum arquivo de configuração necessário" | Nomeie o agente quando ajuda na clareza |

### Padrões de Estilo

| # | Padrão | Antes | Depois |
|---|---------|--------|--------|
| 14 | **Travessões** | "instituições—não as pessoas—mas isso continua—" | Corte: pontos, vírgulas, dois-pontos ou parênteses |
| 15 | **Excesso de negrito** | "**OKRs**, **KPIs**, **BMC**" | "OKRs, KPIs, BMC" |
| 16 | **Listas com cabeçalho na linha** | "**Performance:** A performance melhorou" | Converta pra prosa |
| 17 | **Cabeçalhos em Caixa Alta de Título** | "Negociações Estratégicas E Parcerias" | "Negociações estratégicas e parcerias" |
| 18 | **Emojis** | "🚀 Fase de Lançamento: 💡 Insight Chave:" | Remova os emojis |
| 19 | **Aspas curvas** | `disse "o projeto"` | `disse "o projeto"` |
| 26 | **Pares de palavras hifenizadas** | "multifuncional, orientado-a-dados, voltado-ao-cliente" | Tire os hífens dos pares comuns |
| 27 | **Clichês de autoridade persuasiva** | "No fundo, o que importa é..." | Diga o ponto direto |
| 28 | **Anúncios de sinalização** | "Vamos mergulhar nisso", "Aqui está o que você precisa saber" | Comece pelo conteúdo |
| 29 | **Cabeçalhos fragmentados** | "## Performance" + "Velocidade importa." | Deixe o título fazer o trabalho |
| 30 | **Escrita ancorada em diff** | "Esta função foi adicionada pra substituir..." | Descreva o que ela faz, não o que mudou |
| 31 | **Tiradas fabricadas / drama em staccato** | "Não tinha preferência. Nenhum viés. Nenhuma nostalgia." | Use frases de tamanho variado e afirmações concretas |
| 32 | **Fórmulas de aforismo** | "Simetria é a linguagem da confiança" | Troque a fórmula pela afirmação real |
| 33 | **Aberturas retóricas de conversa** | "Sinceramente? Depende..." | Tire a falsa franqueza de abertura |

### Padrões de Comunicação

| # | Padrão | Antes | Depois |
|---|---------|--------|--------|
| 20 | **Resíduos de chatbot** | "Espero que ajude! Me avise se..." | Remova por completo |
| 21 | **Avisos de corte de conhecimento** | "Embora os detalhes sejam limitados nas fontes disponíveis..." | Ache fontes ou remova |
| 22 | **Tom bajulador** | "Ótima pergunta! Você está absolutamente certo!" | Responda direto |

### Enchimento e Hesitação

| # | Padrão | Antes | Depois |
|---|---------|--------|--------|
| 23 | **Frases de enchimento** | "A fim de", "Devido ao fato de que" | "Pra", "Porque" |
| 24 | **Hesitação excessiva** | "poderia potencialmente possivelmente" | "pode" |
| 25 | **Conclusões genéricas** | "O futuro é promissor" | Planos ou fatos específicos |

## Exemplo completo

**Antes (com cara de IA):**
> Ótima pergunta! Aqui está um texto sobre o tema. Espero que ajude!
>
> A programação assistida por IA serve como um duradouro testemunho do potencial transformador dos grandes modelos de linguagem, marcando um momento decisivo na evolução do desenvolvimento de software. No cenário tecnológico em rápida evolução de hoje, essas ferramentas inovadoras—aninhadas na interseção entre pesquisa e prática—estão remodelando a forma como engenheiros idealizam, iteram e entregam, ressaltando seu papel vital nos fluxos de trabalho modernos.
>
> No fundo, a proposta de valor é clara: otimizar processos, aprimorar a colaboração e fomentar o alinhamento. Não é só sobre autocompletar; é sobre destravar a criatividade em escala, garantindo que as organizações se mantenham ágeis enquanto entregam experiências fluidas, intuitivas e poderosas aos usuários. A ferramenta serve como catalisador. O assistente funciona como parceiro. O sistema se firma como base pra inovação.
>
> Observadores do setor notaram que a adoção acelerou de experimentos amadores a implementações em toda a empresa, de desenvolvedores solo a equipes multifuncionais. A tecnologia foi destaque no The New York Times, na Wired e no The Verge. Além disso, a capacidade de gerar documentação, testes e refatorações evidencia como a IA pode contribuir pra melhores resultados, destacando a intrincada interação entre automação e julgamento humano.
>
> - 💡 **Velocidade:** A geração de código é muito mais rápida, reduzindo o atrito e empoderando os desenvolvedores.
> - 🚀 **Qualidade:** A qualidade da saída foi aprimorada por treinamento melhor, contribuindo pra padrões mais altos.
> - ✅ **Adoção:** O uso continua a crescer, refletindo tendências mais amplas do setor.
>
> Embora os detalhes específicos sejam limitados com base nas informações disponíveis, poderia-se potencialmente argumentar que essas ferramentas talvez tenham algum efeito positivo. Apesar dos desafios típicos de tecnologias emergentes—incluindo alucinações, viés e responsabilização—o ecossistema continua a prosperar. A fim de realizar plenamente esse potencial, as equipes precisam se alinhar às melhores práticas.
>
> Em conclusão, o futuro é promissor. Tempos empolgantes estão por vir enquanto seguimos nessa jornada rumo à excelência. Me avise se quiser que eu expanda alguma seção!

**Depois (humanizado):**
> Os assistentes de código por IA aceleram as partes chatas do trabalho. Eles são ótimos no código repetitivo: arquivos de configuração e aquela cola que você não tem vontade de escrever. Também ajudam a esboçar um teste, mas você ainda tem que ler.
>
> A parte perigosa é o quanto as sugestões parecem confiantes. Já aceitei código que compilou e passou no lint, e só depois percebi que tinha errado o ponto porque eu parei de prestar atenção.
>
> Se você trata como autocomplete e revisa cada linha, é útil. Se usa pra não pensar, ele vai te ajudar a soltar bug mais rápido.
>
> A única rede de segurança de verdade são os testes. Sem eles, você está julgando no feeling.

## Referências

- Guia público "sinais de escrita por IA", mantido por um projeto colaborativo de limpeza de conteúdo gerado por IA. Fonte primária.

## Histórico de versões

- **2.8.0** - Adicionados os padrões de estilo e cadência #31 a #33 (tiradas fabricadas, fórmulas de aforismo e aberturas retóricas de conversa); ampliado o #20 pra pegar os fechamentos de chatbot que se oferecem pra continuar. 33 padrões no total.
- **2.7.0** - Adicionado o padrão #30 (escrita ancorada em diff); travessões viraram corte obrigatório em vez de "usar com moderação"; ampliado o #21 pra cobrir o preenchimento especulativo de lacunas ("mantém um perfil discreto"). 30 padrões no total.
- **2.6.0** - Passada de limpeza: consolidou as seções de fluxo duplicadas, condicionou a orientação de personalidade ao conteúdo em que a voz é desejada, removeu a subseção de impressão digital de modelo e condensou o exemplo trabalhado. Sem mudança nos 29 padrões.
- **2.5.1** - Adicionada a regra de voz passiva e fragmentos sem sujeito, subindo o total pra 29 padrões.
- **2.5.0** - Adicionados os padrões de enquadramento persuasivo, sinalização e cabeçalhos fragmentados; paralelismos negativos ampliados pra cobrir negações no rabo; ajustada a redação sobre o excesso de travessões; corrigida a redação do frontmatter pra usar "frases de enchimento".
- **2.4.0** - Adicionada a calibragem de voz: casar com o estilo de escrita do dono a partir de amostras.
- **2.3.0** - Adicionado o padrão #25: excesso de pares de palavras hifenizadas.
- **2.2.0** - Adicionada uma auditoria final do tipo "obviamente gerado por IA" e o prompt de reescrita de segunda passada.
- **2.1.1** - Corrigido o exemplo do padrão #18 (aspas curvas vs aspas retas).
- **2.1.0** - Adicionados exemplos de antes e depois pra todos os 24 padrões.
- **2.0.0** - Reescrita completa com base no conteúdo bruto do guia.
- **1.0.0** - Versão inicial.

## Licença

MIT
