# THIGAS AI

Assistente de programação distribuído como site e PWA instalável pelo navegador.

**Site:** https://thigas-coder-gateway.onrender.com/

O site usa o layout retro CRT/ASCII, com quatro temas, efeitos opcionais e sons desligados por padrão. As respostas são geradas pela Maritaca AI através do servidor; não há respostas simuladas.

## Conversa no navegador

- Escreva uma pergunta ou cole código. Enter envia; Shift+Enter insere uma linha.
- O clipe lê arquivos de texto/código UTF-8 de até 256 KiB. Mensagem e anexo juntos devem ter até 60.000 caracteres. Imagens, PDF, ZIP e modelos não são interpretados.
- Blocos de código podem ser copiados ou baixados. Nenhum código gerado é executado pelo site.
- Histórico e preferências são salvos somente no navegador atual. LIMPAR apaga a conversa local. Não há sincronização com o histórico do Telegram.
- `/help` mostra os comandos e informações de privacidade.

O conteúdo enviado e parte do histórico são encaminhados à Maritaca. Não envie senhas, chaves ou dados sensíveis. A API consome o saldo do responsável pela chave; publicar o site não torna a inferência gratuita. A hospedagem gratuita pode demorar para despertar.

## Instalar o PWA

Abra o site no Chrome, Edge, Samsung Internet ou Safari e use o botão **INSTALAR**. Quando o navegador não oferecer o prompt automático, o botão mostra as instruções do sistema.

- **Android/Chrome:** menu ⋮ → Instalar aplicativo ou Adicionar à tela inicial.
- **Windows/Chrome ou Edge:** botão de instalação na barra de endereço.
- **iPhone/iPad:** Safari → Compartilhar → Adicionar à Tela de Início.

Depois da primeira visita online com o service worker instalado, a interface e o histórico local podem abrir sem internet. **Novas respostas exigem internet.** Perguntas não são reenviadas automaticamente quando a conexão volta.

Uma nova versão oferece **ATUALIZAR** sem recarregar a conversa automaticamente. Se houver texto não enviado, anexo ou consulta em andamento, o usuário confirma o descarte antes de recarregar. O histórico já salvo permanece.

O projeto Android, arquivos Gradle e workflow de geração do APK foram retirados da branch principal. Isso não desinstala aplicativos já existentes nos aparelhos nem apaga commits históricos. O workflow **Retirar APKs antigos** remove somente os artefatos `THIGAS-Coder-APK` gerados até 03/10/2026 às 00:34:57 no horário de Brasília, usando uma permissão temporária do Actions e sem chaves pessoais. Ele dispara ao alterar o próprio arquivo; o build Android não é retomado.

## Servidor

O servidor Flask em `server/app.py` oferece:

- `GET /`: interface do chat.
- `GET /manifest.webmanifest`: identidade e ícones do PWA.
- `GET /sw.js`: service worker com escopo da raiz.
- `GET /api`: informações JSON do gateway (antes disponíveis na raiz).
- `GET /health`: estado do serviço.
- `POST /chat`: `{ "message": "...", "history": [] }` → `{ "answer": "...", "model": "..." }`.
- `POST /telegram/webhook`: webhook do Telegram, preservado.

As chaves continuam exclusivamente nas variáveis de ambiente do Render, nunca no JavaScript ou repositório. A rota `/chat` é pública: antes de divulgar amplamente, configure limite de gastos na Maritaca e avalie autenticação/controle de uso no servidor. O service worker guarda somente recursos públicos da interface; não intercepta nem coloca mensagens, respostas ou anexos da API no cache.

## Testes locais

```sh
pip install -r server/requirements.txt
python -m unittest discover -s server/tests -v
node --test server/tests/*.test.cjs
```

Os testes usam respostas simuladas **apenas na suíte de testes**, sem consumir a API. Para iniciar localmente:

```sh
python server/app.py
```

Abra `http://127.0.0.1:7860`. Configure `MARITACA_API_KEY` no ambiente para respostas reais. Telegram é opcional no teste local.

O workflow **Verificar PWA THIGAS** executa os testes no GitHub a cada mudança no servidor, ícones ou configuração da suíte.

## Ícones e atualizações

`node scripts/build_pwa_icons.cjs` regenera os ícones de 192×192 e 512×512. Os PNGs prontos ficam versionados para evitar dependências na hospedagem. Consulte `LEIA-ME.md` para o guia de uso.

Ao mudar a interface, altere a versão do cache em `server/static/sw.js`, os parâmetros de versão do HTML e a lista `APP_SHELL` juntos. Somente caches com prefixo `thigas-pwa-` são limpos; o histórico em localStorage não é removido pela atualização.

## Documentos pelo Telegram

O bot agora pode receber XLSX e preparar uma cópia editada por `/planilha`, com revisão e botões de confirmação. `/pdf` gera um PDF real. `/id` informa o ID para configurar a lista de usuários autorizados. Veja [configuração e limites](docs/TELEGRAM_DOCUMENTOS.md).

As ferramentas exigem `THIGAS_TELEGRAM_ALLOWED_USERS` e `TELEGRAM_WEBHOOK_SECRET`. O armazenamento temporário e o plano gratuito atuais não constituem uma implantação 24/7; o guia descreve os componentes que ainda faltam.

## Contas e documentos no navegador

A área `/workspace` oferece cadastro via Google, GitHub e Facebook (Meta), envio de arquivos do aparelho e entrega de PDF, DOCX e XLSX revisado. Requer configuração OAuth e armazenamento persistente para cadastros de produção. Consulte [configuração e limites](docs/CONTAS_E_DOCUMENTOS.md).
