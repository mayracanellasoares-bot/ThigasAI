# Auditoria do site THIGAS AI — 13/10/2026

Escopo: gateway Flask, interface PWA, autenticação por senha, pesquisa online e GitHub Actions.

## Problemas encontrados e correções

- **Métricas ocultas:** chat.css e mini-nano-theme.css escondiam o painel de modelo/tokens e status. Restaurada exibição compacta para computador e celular.
- **Atalho incorreto:** o menu oferecia /limpar, mas somente /clear era reconhecido. Ambos agora funcionam.
- **JSON externo malformado:** respostas inesperadas de Wikipédia/Brave podiam provocar erro interno. Corrigido com validação de estrutura e mensagem controlada.
- **Links e snippets:** normalizados caracteres de controle; endereços locais, inválidos e não HTTPS são bloqueados antes de exibir fontes.
- **Proteção HTTP:** removido cabeçalho CORS genérico de todas as respostas; adicionados nosniff, X-Frame-Options, Referrer-Policy e Permissions-Policy.
- **Cache de interface:** versões de arquivos CSS/JS alteradas para melhorar atualização do layout após deploy.

## Verificação

- Novos testes Python e Node asseguram que alterações de interface e verificações de segurança não regridem.
- scripts/smoke_site.py testa apenas /health, /entrar, /static/login.js, /api e /, sem login nem acesso pago à LLM.
- O smoke público é separado da suíte unitária e não bloqueia CI caso o Render esteja temporariamente indisponível; seu resultado precisa ser lido no log.
- Testes automatizados de gateway usam respostas simuladas, não medem a inteligência real dos modelos.

## Limitações

Merge no GitHub não é comprovante de deploy no Render. Verificar a implantação, logs e métricas reais requer seleção confirmada do workspace Render. A pesquisa sem chave externa continua restrita à Wikipédia, não à internet toda.