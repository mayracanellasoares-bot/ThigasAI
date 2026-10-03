# THIGAS AI

Assistente de programação disponível no navegador, Telegram e APK Android.

**Site:** https://thigas-coder-gateway.onrender.com/

O site usa o layout retro CRT/ASCII, com quatro temas, efeitos opcionais e sons desligados por padrão. As respostas são geradas pela Maritaca AI através do servidor; não há respostas simuladas.

## Conversa no navegador

- Escreva uma pergunta ou cole código. Enter envia; Shift+Enter insere uma linha.
- O clipe lê arquivos de texto/código UTF-8 de até 256 KiB. Mensagem e anexo juntos devem ter até 60.000 caracteres. Imagens, PDF, ZIP e modelos não são interpretados.
- Blocos de código podem ser copiados ou baixados. Nenhum código gerado é executado pelo site.
- Histórico e preferências são salvos somente no navegador atual. LIMPAR apaga a conversa local. Não há sincronização com o histórico do Telegram.
- `/help` mostra os comandos e informações de privacidade.

O conteúdo enviado e parte do histórico são encaminhados à Maritaca. Não envie senhas, chaves ou dados sensíveis. A API consome o saldo do responsável pela chave; publicar o site não torna a inferência gratuita. A hospedagem gratuita pode demorar para despertar.

## Servidor e compatibilidade

O servidor Flask em `server/app.py` oferece:

- `GET /`: interface do chat.
- `GET /api`: informações JSON do gateway (antes disponíveis na raiz).
- `GET /health`: estado do serviço.
- `POST /chat`: contrato preservado para o APK: `{ "message": "...", "history": [] }` → `{ "answer": "...", "model": "..." }`.
- `POST /telegram/webhook`: webhook do Telegram, preservado.

As chaves continuam exclusivamente nas variáveis de ambiente do Render, nunca no JavaScript, APK ou repositório. A rota `/chat` é pública: antes de divulgar amplamente, configure limite de gastos na Maritaca e avalie autenticação/controle de uso no servidor.

## Testes locais

```sh
pip install -r server/requirements.txt
python -m unittest discover -s server/tests -v
node --test server/tests/chat.test.cjs
```

Os testes usam respostas simuladas **apenas na suíte de testes**, sem consumir a API. Para iniciar localmente:

```sh
python server/app.py
```

Abra `http://127.0.0.1:7860`. Configure `MARITACA_API_KEY` no ambiente para respostas reais. Telegram é opcional no teste local.

## APK

APK online para Android 8.0 ou superior. Consulte `LEIA-ME.md`. Compilação em **Actions > Gerar APK THIGAS**. O site novo não altera o endpoint `/chat` usado pelo aplicativo.
