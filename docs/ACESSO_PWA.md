# THIGAS AI — login e senha única no PWA

## Situação da implementação

Esta alteração exige configuração manual **antes** de habilitar a proteção em produção. Nenhuma senha é gravada no repositório, no HTML, no JavaScript ou no manifest do PWA.

O mesmo usuário e a mesma senha permitem entrar tanto no navegador quanto no THIGAS AI instalado pela opção **Instalar aplicativo**. Trata-se de uma conta compartilhada, **não** de cadastro individual. Quem conhecer as credenciais terá acesso aos recursos do gateway.

## Configuração no Render

No serviço \`thigas-coder-gateway\`, abra **Environment** e configure:

| Variável | Valor | Observação |
| --- | --- | --- |
| \`THIGAS_ACCESS_ENABLED\` | \`true\` | ativa a proteção; sem isso o site continua público |
| \`THIGAS_ACCESS_USERNAME\` | \`thigas\` | usuário compartilhado (pode ser alterado) |
| \`THIGAS_ACCESS_PASSWORD\` | senha privada com **no mínimo 12 caracteres** | **não** salvar no GitHub |
| \`THIGAS_SESSION_SECRET\` | segredo aleatório com **no mínimo 32 caracteres** | pode reutilizar o segredo já configurado para documentos |

No Render, use **Save, deploy** após configurar as quatro variáveis. A opção \`false\` desativa o controle de acesso. Se a proteção estiver ativa e faltar usuário, senha ou segredo de sessão, as rotas protegidas retornarão **503** em vez de abrir o acesso.

**Atenção:** editar \`render.yaml\` não garante a atualização de variáveis de um serviço já criado manualmente. Verifique o painel *Environment* do serviço.

## Como funciona

1. O acesso a \`/\` ou \`/workspace\` sem sessão leva a \`/login\`.
2. A senha é comparada apenas no backend, com comparação de tempo constante.
3. O backend envia um cookie assinado e protegido por \`Secure\`, \`HttpOnly\` e \`SameSite=Lax\`. A sessão expira após 12 horas.
4. \`/chat\`, \`/api\`, extração de documentos, imagem, análise de links e operações da área de documentos exigem sessão autenticada.
5. \`/health\` permanece público para monitoramento. \`/telegram/webhook\` conserva seu próprio token secreto, independentemente do login web.
6. O botão **Encerrar sessão** invalida o cookie local. Cinco tentativas erradas por endereço IP em dez minutos acionam bloqueio temporário.
7. A instalação PWA não incorpora senha alguma no pacote. É necessário autenticar-se ao abrir o aplicativo. Sem conexão, não é possível validar o acesso.

## Privacidade e limitações

- O histórico do chat continua salvo no \`localStorage\` do próprio navegador e **não é criptografado**. Para dispositivos compartilhados, remova os dados do site nas configurações do navegador. Sair do aplicativo não apaga automaticamente esse armazenamento.
- O Service Worker da nova versão salva **somente CSS, JavaScript, ícones e manifest públicos**. HTML de chat, login, documentos e respostas nunca são colocados em cache. Ele remove os caches \`thigas-pwa-*\` anteriores assim que a atualização é ativada.
- Versões já instaladas podem continuar exibindo a página HTML antiga enquanto estiverem completamente offline e ainda não tiverem recebido o novo Service Worker; APIs continuam bloqueadas pelo servidor.
- A limitação de tentativas é em memória do processo web. Em múltiplas instâncias, use um armazenamento compartilhado (por exemplo, Redis).
- Senha compartilhada não oferece auditoria nem revogação por usuário. Se precisar de contas individuais, substitua por autenticação própria com identidades distintas.
- Ao **alterar a senha**, rotacione também \`THIGAS_SESSION_SECRET\` para invalidar todas as sessões antigas.

## Validação após habilitar

1. Em aba anônima, \`/\` deve redirecionar para \`/login\`.
2. Teste usuário/senha errados: mensagem genérica e HTTP 401.
3. Teste credenciais certas: redirecionamento para o chat, cookie seguro.
4. Com sessão encerrada, \`POST /chat\` deve responder 401, sem consumir tokens.
5. Teste \`/workspace\`, \`/api\` e \`/static/index.html\`: não devem abrir dados privados sem login.
6. Instale o PWA, encerre a sessão, reabra online e confirme a exigência de login.
7. Ative a nova versão do PWA e desconecte a internet: o chat não deve aparecer a partir do cache.
8. Confira \`/health\` e o webhook do Telegram para assegurar que continuam operacionais.

O rollout deve seguir a ordem: configurar segredos no Render, revisar os testes do PR, integrar a branch, habilitar \`THIGAS_ACCESS_ENABLED=true\` e validar a produção.
