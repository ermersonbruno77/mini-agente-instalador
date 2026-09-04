# Checklist de auditoria de acesso e segurança

Método adaptado de uma metodologia de teste de segurança de aplicações open source
(ordem de prioridade, classes de falha perseguidas, padrão de prova). Traduzido
para qualquer sistema com múltiplos perfis de acesso e um backend + banco por
trás — troque os nomes de tabela/campo dos exemplos pelos do seu sistema real.

**Regra de entrada: achado sem prova de conceito não entra no relatório.** Prova
é requisição real e resposta real ("200 não prova que subiu, prova é tela
logada"). Suspeita vira item de "a confirmar", nunca vira linha de achado.

**Limites que não mudam ao rodar isto:** só leitura, nunca contra produção sem
aviso, nunca escrita no banco, nenhuma exploração de fato (sem exfiltrar dado
real, sem derrubar sessão de gente real). Onde o teste pode ter efeito colateral
em dado real, roda com conta de teste criada pra isso, nunca com a conta do
Chefe ou de um gestor real.

Antes de rodar: confirme as URLs atuais do sistema em `memory/projects.md`,
nunca suponha endereço de cabeça.

---

## A. Escopo de dado entre perfis (prioridade 1 — dado de pessoa exposto)

1. **Acesso direto ao banco via API pública, sem passar pelo backend.** Se o
   banco expõe uma API REST direta (ex.: Supabase/PostgREST), pegar a chave
   pública do cliente (bundle do front) e bater direto na tabela sensível com
   essa chave e sem sessão de usuário nenhum. Prova: linhas retornadas fora do
   backend. Se vier vazio/403, a política de acesso está segurando; se vier
   linha, é achado de prioridade máxima.
2. **Política de acesso por operação, não só por leitura.** Repetir o mesmo
   teste com escrita/exclusão no mesmo endpoint. Política que cobre leitura e
   esquece escrita é o padrão de falha mais comum nesse tipo de API.
3. **Mass assignment em registro de pessoa.** Autenticado como usuário comum,
   dar update no próprio registro (ex. atualizar telefone) incluindo no mesmo
   corpo um campo que não devia poder mudar por essa tela (um campo sensível
   qualquer: valor, papel, permissão). Prova: leitura seguinte mostrando o
   campo extra persistido.
4. **IDOR (referência direta a objeto de outro escopo).** Logado como usuário
   de um grupo/time A, trocar o identificador de grupo/time na query ou no
   path pelo de um grupo B. Prova: dado do grupo B retornado. Repetir em pelo
   menos dois formatos de referência (path param e query param), porque a
   checagem pode existir só em um.
5. **Ação de um perfil, chamada por outro (BFLA).** Com token de um usuário
   "leitura", chamar direto a rota de ação que só o botão do perfil "editor"
   mostra. Prova: a ação de fato altera estado (conferir com leitura logo
   depois), não só o retorno de sucesso da chamada.
6. **Overfetch no payload de tela de leitura.** Abrir o DevTools na tela de um
   perfil restrito e ler o JSON bruto da resposta, não só o que a tela
   desenha. Prova: campo sensível presente no payload de uma tela que não o
   exibe.

## B. Autenticação x autorização, sessão

7. **Sessão de um sistema usada em outro.** Se existe mais de um sistema
   compartilhando a mesma base de sessão, pegar o cookie de sessão válido de
   um perfil e chamar um endpoint de outro sistema com o mesmo cookie. Prova:
   sucesso com dado do outro sistema.
8. **API direta sem middleware.** `curl` direto no endpoint do backend sem
   sessão de navegador, só com token de máquina/serviço. Prova: sucesso com
   dado de pessoa quando deveria recusar.
9. **Provedor de login autentica, mas quem autoriza é o sistema.** Criar/usar
   um e-mail que passa pelo provedor de autenticação (login com sucesso) mas
   não existe no cadastro interno de usuários do sistema. Prova: tela final é
   "sem acesso" **e** qualquer chamada de API feita com o token desse login
   (via `curl`, não só pela tela) também recusa. Se a tela barra mas a API
   aceita, o controle está só no front.
10. **Token do provedor de auth, audiência e emissor.** Conferir no backend
    (ler o código, não adivinhar) se o servidor valida emissor/audiência do
    token, ou só a assinatura. Se só assinatura, testar token válido de
    outro projeto/app do mesmo provedor contra o endpoint, se existir um de
    teste — não inventar chave, só usar o que já existir.
11. **Logout do lado do servidor.** Fazer logout, guardar o token/cookie
    antigo, chamar um endpoint autenticado com ele depois. Prova: se o pedido
    ainda passa, a sessão não foi revogada no backend, só apagada no browser.

## C. Superfície exposta

12. **Documentação viva em produção.** Rotas de schema/documentação
    automática (`/openapi.json`, `/docs`, `/redoc`) no domínio de produção.
    Prova: schema completo acessível sem login, incluindo rotas
    administrativas que a UI esconde.
13. **Rotas escondidas por flag de "fora do schema".** Se o item 12 mostrar
    prefixos administrativos, tentar variações plausíveis mesmo sem
    aparecerem no schema. Prova: resposta de dado real, não 404.
14. **Proteção de deploy de preview.** Pegar a URL de um deploy de preview
    recente e acessar sem estar logado na plataforma de deploy. Prova: tela
    ou dado carregando sem SSO/senha de preview.
15. **Variável de ambiente por ambiente, não por existência.** Para cada env
    var sensível do projeto, conferir se está presente em TODOS os ambientes
    (dev/preview/produção). Prova de furo: falta em um ambiente enquanto as
    chaves de auth existem nos outros.
16. **Chave de serviço vazada no bundle do cliente.** `grep` nos arquivos
    estáticos servidos publicamente por termos como `SERVICE_ROLE`, `SECRET`,
    `sk_live`, `sk_test`. Prova: string da chave aparecendo em arquivo
    servido sem autenticação.
17. **Bucket/storage público.** Se o sistema usa armazenamento de objeto,
    testar acesso a arquivo plausível sem token, e listagem de prefixo sem
    autenticação.

## D. Credenciais

18. **Credencial entregue por canal informal sem tela de troca de senha.**
    Confirmar se continua sem forma de o dono trocar a própria senha. Não é
    achado novo a cada rodada, é item de dívida: só reabrir quando o estado
    mudar.
19. **Segredo sem consumidor no `.env`.** Para cada variável nova desde a
    última auditoria, `grep` pelo nome dela em todo o(s) repositório(s) do
    projeto. Prova de achado: zero ocorrências de uso — o segredo está
    guardado sem ninguém ler.

## E. Robustez de fluxo (menor prioridade, mas parte do método)

20. **Race condition em ação de estado único.** Disparar duas requisições
    simultâneas contra uma ação que devia ser feita uma vez só. Prova: os
    dois pedidos completam com sucesso e o estado final reflete dupla
    execução (dois registros, contador duplicado).
21. **Rate limit / força bruta no login.** Confirmar se existe limite de
    tentativas por usuário/IP no login. Prova: N tentativas de senha errada
    seguidas sem bloqueio nem atraso crescente. Não usar conta real de
    ninguém pra esse teste.

---

## Como registrar um achado

Para cada item marcado como furo:

1. A requisição exata (método, URL, headers relevantes sem o valor do
   segredo) e a resposta que voltou.
2. Quem consegue fazer aquilo, com que credencial (perfil, não nome de
   pessoa).
3. O dado que fica exposto, nomeado de forma específica (ex.: "campo de valor
   de 40 registros de um grupo", não "dados sensíveis").
4. A correção mínima proposta, e o que ela quebra se aplicada — testada
   também com o dono legítimo antes de virar recomendação.

Achado sem os 4 pontos não é achado, é suspeita. Suspeita vira pergunta para o
time de dev, não vira linha no relatório.
