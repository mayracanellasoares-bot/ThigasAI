# Dossiê técnico e de autoria — THIGAS AI

**Status:** documento de organização de evidências e histórico do projeto.  
**Data de elaboração:** 2026-10-03  
**Repositório:** https://github.com/mayracanellasoares-bot/ThigasAI

> Este documento não é certificado de registro, parecer jurídico nem substitui eventual registro oficial. Ele reúne informações técnicas, decisões de projeto e orientações para preservação de evidências.

## 1. Identificação do projeto

- **Nome do projeto:** THIGAS AI
- **Produto atual:** THIGAS Coder
- **Repositório de referência:** \`mayracanellasoares-bot/ThigasAI\`
- **Objetivo:** disponibilizar um assistente de programação em português do Brasil, acessível por aplicativo Android e por uma interface online.
- **Estado atual documentado:** aplicativo Android conectado a um gateway próprio, que encaminha as solicitações para o serviço de modelo configurado no servidor.
- **Titular/autoria declarada:** **PREENCHER E CONFIRMAR**
- **Possibilidade de titularidade conjunta:** **PREENCHER, SE APLICÁVEL**
- **Responsável pela organização deste repositório:** conta GitHub \`mayracanellasoares-bot\`

A titularidade deve ser confirmada antes de qualquer declaração oficial. Não incluir CPF, endereço, telefone, tokens ou chaves neste repositório público.

## 2. Escopo do dossiê

Este dossiê registra:

1. a finalidade e a arquitetura do THIGAS AI;
2. os componentes próprios e os componentes de terceiros;
3. as versões e os marcos de desenvolvimento observáveis no repositório;
4. as evidências que devem ser preservadas;
5. os campos ainda pendentes para uma eventual proteção ou registro formal.

## 3. Arquitetura técnica

### 3.1 Aplicativo Android

O aplicativo Android funciona como a interface de uso do THIGAS Coder. Ele possui:

- tela de conversa;
- criação de nova conversa;
- histórico local de mensagens;
- tema visual claro;
- identidade visual e mascote;
- envio de texto;
- seleção de arquivos de texto e código para anexar à mensagem;
- comunicação HTTPS com o gateway configurado;
- tratamento de respostas e mensagens de falha de conexão.

Principais áreas do repositório:

- \`app/src/main/java/\`
- \`app/src/main/res/\`
- \`app/src/main/AndroidManifest.xml\`
- \`app/build.gradle\`
- \`settings.gradle\`
- \`gradle/\`

### 3.2 Gateway de servidor

O gateway em Python recebe a mensagem do aplicativo e chama o provedor de modelo configurado por variável de ambiente.

Principais características:

- endpoint de conversa;
- validação de entrada;
- limite de tamanho de mensagem;
- prompt de sistema do THIGAS Coder;
- limite configurável de tokens de resposta;
- timeout para o provedor upstream;
- mensagens de erro sem expor a chave da API;
- configuração para execução no Render.

Arquivo principal:

- \`server/app.py\`

Arquivos de implantação e dependências:

- \`server/requirements.txt\`
- \`render.yaml\`

### 3.3 Construção e distribuição

O repositório contém configuração para gerar o APK por integração contínua:

- \`.github/workflows/android.yml\`

Os artefatos de compilação devem ser tratados como versões do produto. Para cada versão distribuída, preservar:

- arquivo APK;
- nome e versão do aplicativo;
- commit usado na compilação;
- data da compilação;
- hash SHA-256 do APK.

## 4. Funcionalidades e decisões de produto

### Funcionalidades próprias declaradas

- marca e nome THIGAS AI/THIGAS Coder;
- identidade visual e mascote usados pelo aplicativo;
- organização da experiência de conversa;
- fluxo de nova conversa;
- armazenamento local do histórico;
- seleção e leitura de arquivos de texto/código no aplicativo;
- prompt de comportamento do assistente;
- integração entre aplicativo, gateway e provedor de modelo;
- mensagens de erro e orientação ao usuário;
- configuração de build e empacotamento do aplicativo;
- documentação e organização deste projeto.

### Funcionalidades não atribuídas como criação própria

Não declarar como propriedade exclusiva do projeto:

- modelos de linguagem de terceiros;
- pesos dos modelos;
- tokenizadores;
- APIs de provedores;
- Android SDK;
- bibliotecas Python, Java/Kotlin e JavaScript;
- GitHub Actions;
- Render;
- códigos copiados de terceiros;
- logos e marcas de terceiros;
- Telegram ou outras plataformas, caso sejam adicionados posteriormente.

## 5. Componentes e serviços de terceiros

Os itens abaixo pertencem aos respectivos autores, projetos ou empresas e devem continuar sujeitos às licenças e aos termos aplicáveis:

| Componente | Uso no projeto | Tratamento |
|---|---|---|
| Android SDK/Gradle | compilação e execução do app | respeitar licenças do Android e das ferramentas |
| Python, Flask e Requests | gateway HTTP | preservar avisos e licenças das dependências |
| Gunicorn | servidor de produção, se usado | preservar licença da dependência |
| Render | hospedagem do gateway | serviço de infraestrutura; não é autoria do projeto |
| Maritaca AI | provedor/modelo de geração | obedecer contrato, limites e política do provedor |
| Hugging Face | modelos ou hospedagem, se utilizados | verificar licença individual de cada modelo |
| GitHub Actions | automação de build | serviço de automação; verificar configuração e limites |
| Telegram | integração futura, se implementada | respeitar API e termos da plataforma |

Antes de uma publicação comercial, gerar um inventário das licenças efetivamente instaladas. A tabela acima é uma classificação inicial, não uma auditoria jurídica.

## 6. Histórico técnico resumido

O projeto passou pelas seguintes fases de desenvolvimento:

1. protótipos de modelos locais e testes em Termux;
2. experimentos com MiniMind e modelos pequenos;
3. experimentos com RAG e consulta documental;
4. testes de modelos de programação, incluindo modelos da família Qwen;
5. criação de interface online;
6. criação do aplicativo Android;
7. criação do gateway próprio para separar o aplicativo da chave do provedor;
8. ajustes de interface, histórico, anexos, limites de resposta e mensagens de erro;
9. automação de compilação do APK.

Os commits do GitHub são a fonte cronológica principal. Para cada marco importante, preservar também uma cópia exportada do código e o hash do arquivo compactado.

## 7. Evidências recomendadas

Preservar, em local privado e com cópia de segurança:

- exportação do repositório em formato ZIP;
- data e hora da exportação;
- URL do repositório;
- lista de commits e respectivos hashes;
- APK de cada versão publicada;
- hash SHA-256 de cada APK e ZIP;
- capturas de tela datadas do aplicativo;
- descrição de quem criou cada parte original;
- comprovantes de criação de identidade visual, textos e mascote;
- arquivos de configuração sem segredos;
- lista de dependências e licenças;
- registros de implantação sem tokens ou chaves.

### Como calcular o hash

No Windows PowerShell:

\`\`\`powershell
Get-FileHash .\\THIGAS_AI_v2.2.apk -Algorithm SHA256
Get-FileHash .\\THIGAS_AI_dossie.zip -Algorithm SHA256
\`\`\`

No Linux, Termux ou Chromebook:

\`\`\`bash
sha256sum THIGAS_AI_v2.2.apk
sha256sum THIGAS_AI_dossie.zip
\`\`\`

Guardar o resultado junto com a data, o nome do arquivo e o commit correspondente.

## 8. Segurança e segredos

Este repositório não deve conter:

- \`MARITACA_API_KEY\`;
- \`TELEGRAM_BOT_TOKEN\`;
- tokens do GitHub;
- credenciais do Render;
- chaves privadas;
- arquivos \`.env\` com valores reais;
- CPF, endereço ou documentos pessoais.

As chaves devem permanecer somente nos Secrets/Environment Variables do serviço de hospedagem ou em um gerenciador seguro. Se uma chave for publicada por engano, revogá-la e gerar outra imediatamente.

## 9. Campos pendentes

Preencher em uma cópia privada ou após confirmar a titularidade:

- [ ] nome completo do titular;
- [ ] eventual coautor ou titular conjunto;
- [ ] data aproximada da primeira criação;
- [ ] data do primeiro commit ou primeiro arquivo preservado;
- [ ] versão que será considerada a versão de referência;
- [ ] inventário final de dependências;
- [ ] licenças dos modelos de linguagem usados;
- [ ] hashes do ZIP, APK e arquivos de evidência;
- [ ] decisão sobre manter o repositório público ou privado;
- [ ] avaliação sobre registro formal de programa de computador;
- [ ] número do protocolo ou registro oficial, se houver no futuro.

Dados pessoais e documentos de identificação devem ser enviados somente em canal privado e não devem ser colocados neste arquivo público.

## 10. Próximas ações recomendadas

1. Confirmar quem será o titular legal: Thiago Fillipe Soares, Mayra Rejane Ramires Canella Soares ou titularidade conjunta.
2. Criar uma cópia privada do repositório no estado da versão de referência.
3. Exportar o código e o APK dessa versão.
4. Calcular e registrar os hashes.
5. Conferir as licenças das dependências e do modelo efetivamente usado.
6. Guardar capturas de tela e uma descrição do funcionamento.
7. Se desejado, consultar as orientações oficiais do INPI sobre registro de programa de computador:
   - https://www.gov.br/inpi/pt-br/servicos/programas-de-computador/guia-basico
   - https://www.gov.br/pt-br/servicos/solicitar-o-registro-de-programa-de-computador
8. Procurar orientação profissional antes de apresentar uma declaração de titularidade ou fazer pedido formal.

## 11. Declaração de escopo

Este dossiê documenta a organização técnica, o histórico e as evidências do projeto THIGAS AI. Ele não declara que o titular possui direitos sobre modelos, bibliotecas, plataformas, marcas ou serviços de terceiros. A declaração de autoria deve ser completada somente depois de confirmar quem participou da criação e qual titularidade será adotada.

---

**Versão do dossiê:** 1.0  
**Última revisão:** 2026-10-03
