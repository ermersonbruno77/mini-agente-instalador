# AGENTS.md

Orientações pra agentes de IA de programação que trabalham neste repositório.

## O que é este repositório

Uma skill implementada inteiramente em Markdown. O artefato que roda é o `SKILL.md`: o agente lê o frontmatter YAML (metadados e ferramentas permitidas) seguido do prompt de edição. Não há etapa de build nem código pra executar.

## Arquivos principais

- `SKILL.md` é a própria skill. Frontmatter YAML (`name`, `version`, `description`, `allowed-tools`) seguido da lista numerada e canônica de padrões com exemplos de antes e depois. **Esta é a fonte da verdade.**
- `README.md` é pra humanos: instalação, uso, uma tabela resumo dos padrões e um histórico de versões.

## O contrato de manutenção

`SKILL.md` e `README.md` precisam ficar em sincronia. Quando você mudar comportamento ou conteúdo:

- **Padrões:** a skill define hoje **33 padrões numerados**. Se você adicionar, remover ou renumerar qualquer um, atualize a tabela de padrões do README, o título "N Padrões Detectados" e toda referência cruzada na mesma mudança. Mantenha a numeração estável a menos que esteja renumerando de propósito.
- **Versão:** o frontmatter do `SKILL.md` tem um campo `version:` e o `README.md` tem uma seção "Histórico de versões". Suba os dois juntos.
- **Correções não óbvias:** se você mudar o prompt pra tratar um modo de falha complicado (uma edição errada que se repete, uma mudança de tom inesperada), adicione uma nota curta no histórico de versões do README explicando o que foi corrigido e por quê.

## Editando o SKILL.md

- Preserve o frontmatter YAML válido (formatação e indentação).
- O prompt abaixo do frontmatter é o produto. Edite como um documento de instruções cuidadoso, não como código.
