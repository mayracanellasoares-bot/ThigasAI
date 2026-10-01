# THIGAS Coder para Android

Este projeto gera um APK de teste que abre seu THIGAS online em uma WebView. O Qwen permanece no Hugging Face; internet, disponibilidade do Space e cotas de GPU continuam necessárias. Não contém chave de API nem pesos do modelo. Android mínimo: 8.0.

## Gerar pelo GitHub sem Android Studio

1. Crie um repositório PUBLIC no https://github.com/new chamado `thigas-coder-android`.
2. Extraia este ZIP no Windows. Abra a pasta THIGAS_Coder_Android.
3. No GitHub, use Add file > Upload files. Envie o CONTEÚDO dessa pasta: app, build.gradle, settings.gradle, gradle.properties e LEIA-ME.md. Não envie o ZIP nem a pasta externa inteira. Commit changes.
4. Para garantir que o workflow seja incluído, use Add file > Create new file no repositório. Nomeie `.github/workflows/android.yml`. Copie todo o conteúdo do arquivo `GERAR_APK.txt` deste pacote e confirme Commit changes. Se o workflow já foi enviado, pule esta etapa.
5. Abra Actions > Gerar APK THIGAS. Se não começar automaticamente, clique Run workflow > Run workflow. Aguarde a conclusão verde.
6. Abra a execução concluída e, em Artifacts, baixe THIGAS-Coder-APK (precisa estar conectado ao GitHub). Extraia o ZIP baixado: dentro estará app-debug.apk.
7. Transfira app-debug.apk para o Android, abra e permita a instalação por esse aplicativo quando solicitado.

O fluxo usa runner Ubuntu padrão. Execução em repositórios públicos é gratuita nas regras atuais do GitHub. O artefato fica disponível por 7 dias; depois disso, gere novamente ou guarde o APK baixado.

## Conferir no celular

- Abra o aplicativo: deve aparecer o chat THIGAS.
- Pergunte: "Crie uma função Python que some dois números".
- Teste Recarregar, teclado, rotação da tela e voltar.
- Sem internet: deve aparecer Tentar novamente. Reconecte e toque no botão.
- Se login ou cota da GPU impedir o uso, tente Abrir no navegador.

## Limites e manutenção

APK de teste, assinado com chave de debug pelo build. Para atualizar uma instalação com assinatura diferente, pode ser necessário desinstalar a anterior. Para distribuição contínua, configure assinatura de release estável.

O APK não corrige erros do app.py. Seu Space precisa abrir normalmente. URL configurada: https://thiagollipe-thigas-coder.hf.space/ . Se o Space for renomeado, altere APP_URL em app/src/main/java/br/com/thigas/coder/MainActivity.java.

Verificação entregue: XML e estrutura do pacote conferidos; compilação e lint ocorrerão no GitHub Actions. Não foi executado em emulador ou dispositivo nesta entrega.

Versões: JDK 17, Gradle 8.9, Android Gradle Plugin 8.7.3, SDK 35. Com Android SDK e Gradle instalados localmente, rode `gradle :app:lintDebug :app:assembleDebug`.
