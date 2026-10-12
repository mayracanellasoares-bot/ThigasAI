# THIGAS AI — Avaliação v2: contexto e qualidade da geração

**Data:** 12/10/2026. **Projeto:** Brittech.inc / THIGAS AI.

## Resultados com evidências disponíveis

A versão anterior do backend selecionava as últimas 12 mensagens da conversa; fatos antigos deixavam de ser encaminhados ao modelo. O cliente web também aplicava esse corte, impedindo recuperação posterior pelo servidor.

A versão v2 envia até 40 mensagens locais (limitadas a 120 mil caracteres antes do orçamento da pergunta) e o servidor seleciona **no máximo 12 mensagens** e até **60 mil caracteres incluindo a pergunta atual**. As três trocas mais recentes são priorizadas; trocas anteriores só entram se couberem, utilizando coincidência lexical de termos significativos, com ordem cronológica e pares user/assistant intactos. Nenhuma informação é inventada nem armazenada no servidor.

O comparativo reproduzível é:

```bash
python scripts/bench_context_retention.py
```

Ele mede *recuperação de fato antigo dentro do contexto enviado*, **não** a precisão da resposta da LLM. Usa 8 conversas artificiais iguais nos dois algoritmos, medindo retenção do fato e tempo local de seleção. O CI executa a medição e imprime os valores reais no GitHub Actions. Resultados não autorizam afirmar +X% de raciocínio geral.

A verificação de qualidade da geração identifica indicadores:
- `output_limit`: finalização do provedor por limite de saída (`finish_reason=length`).
- `possible_repetition`: três repetições contíguas de texto longo fora de blocos de código.
- `unclosed_code_block`: Markdown com número ímpar de delimitadores de código.
- `possible_python_syntax_error`: parser AST do Python detecta sintaxe inválida em um bloco de código `python`/ `py` fechado.

Os sinais são **heurísticos**. Não comprovam alucinação, bug semântico ou fato incorreto. O backend retorna `quality_flags` e o PWA exibe alerta legível, sem alterar a resposta e **sem novas chamadas cobradas**. Não executa código do modelo; a sintaxe é apenas analisada com `ast.parse`.

## Comparação de inferência real — ainda não executada

O acesso ao chat do THIGAS AI requer senha única protegida, e a API upstream (Maritaca e eventualmente nuvem) pode cobrar créditos. **Não realizamos chamadas autenticadas pagas ou testes contra a API real sem autorização explícita e um ambiente adequado.** Resultados de acurácia, tokens/s e custo upstream antes/depois permanecem não medidos.

Para medir os dois commits de forma válida, use a **mesma configuração do provedor**, chave protegida, mesmos 15 casos de teste, sem treinar neles. Execute a versão antiga em um serviço isolado com acesso autorizado, e a atual em outro, guardando a saída JSONL (fora do repositório público).

- Baseline anterior: commit `c2ac8cbf1d8756dbda3a53a378bda193ab7cd8c7` (antes da evolução aritmética inicial).
- Nova versão: commit da PR de evolução v2 após integração.
- Registre provedor/modelo, temperatura, limites de tokens, hora, tipo de hardware e eventuais caches. Compare tarefas não matemáticas separadamente para não confundir uso da calculadora com evolução neural.

```bash
# Executar em cada versão, no respectivo checkout (ou com script atual copiado):
export THIGAS_ACCESS_PASSWORD='senha-local-nao-registrada'
python scripts/evaluate_cognition.py --split test --live --allow-provider-costs \
  --url http://127.0.0.1:7860 --output baseline_test.jsonl

# Na nova versão, gravar candidato_test.jsonl e comparar:
python scripts/compare_cognition.py \
  --before baseline_test.jsonl --after candidato_test.jsonl --split test
```

Essas opções de execução podem consumir créditos reais e não foram usadas no CI. `compare_cognition.py` só compara respostas pareadas. Não gera respostas, nem preenche medições ausentes; apresenta sinalização explícita de dados incompletos.

## Critérios de aceitação e limitações

1. Todos os testes Python e Node continuam aprovados; a seleção do histórico não pode ultrapassar 12 mensagens nem gerar mensagem `system` a partir do histórico.
2. Casos sintéticos demonstram preservação de fatos relevantes antigos, sem substituir uma avaliação real do modelo.
3. `quality_flags` são estáveis, opcionais para clientes antigos; nunca alteram medição de `usage` proveniente do provedor.
4. Sem API paga, benchmark de seletores **não fornece** acurácia ou latência de inferência LLM.
5. A seleção lexical pode falhar com paráfrases que não compartilham palavras; análise de código com `ast.parse` não testa lógica, dependências ou execução; repetições intencionais podem gerar alerta.
6. Histórico continua armazenado no navegador do usuário; o aplicativo envia até 40 mensagens do histórico atual para o gateway. Revise a política de privacidade para essa ampliação de contexto. Não inclua senhas nem dados sensíveis nas mensagens.

O próximo passo experimental, após consentimento para uso do provedor e autenticação, é rodar pares de consultas nas duas revisões e comparar acurácia por categoria, taxa de loops, tempo e consumo reais.
