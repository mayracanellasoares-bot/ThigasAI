# THIGAS AI — Auditoria e primeira evolução cognitiva

**Data:** 12/10/2026 · **Organização informada:** Brittech.inc  
**Repositório:** mayracanellasoares-bot/ThigasAI  
**Escopo:** gateway Python/Flask e testes. Não há treinamento nem alteração de pesos nesta etapa.

## Evidências verificadas no código da branch main

- Backend `server/app.py`, interface em `server/static`, testes em `server/tests`.
- Inferência via Maritaca Sabiá 4 (configuração padrão) e provedor de nuvem opcional; não há arquitetura Transformer própria no repositório examinado.
- O payload contém `temperature=0.2`, `max_tokens` limitado pela aplicação a 16.384 e `stream=false`.
- O histórico enviado pelo backend é limitado às 12 mensagens mais recentes e a 60.000 caracteres, **não tokens medidos**. O sistema não tem tokenizer do provedor no repositório.
- Métricas de tokens no chat são repassadas do campo `usage` do provedor; se ausentes, permanecem nulas.
- Existem testes de gateway, PWA, arquivos, links e fluxo de histórico, majoritariamente com respostas simuladas.
- **Não há** código de treino Transformer, dados originais de pré-treino, arquivo GGUF, tokenizer treinável nem checkpoint dos pesos na árvore pública analisada.
- Portanto não foi possível comprovar origem dos pesos, quantidade de parâmetros, número de camadas/cabeças, função de perda, otimizador ou capacidade real do modelo neural.

## Gargalos e interpretação

| Observação confirmada | Risco | Natureza |
|---|---|---|
| Respostas externas não passam por verificador aritmético determinístico | Erro numérico pode passar sem detecção | Limitação do gateway |
| Até 16.384 tokens de saída por requisição | Saídas potencialmente longas/caras; tamanho sozinho não assegura precisão | Configuração, não desempenho observado |
| Orçamento de contexto por caracteres e no máximo 12 mensagens | Informações antigas podem ser perdidas | Limitação de contexto no gateway |
| Não há suíte de benchmark cognitivo com respostas reais registradas | Não é possível medir ganho ou regressão em raciocínio | Ausência de observabilidade |
| Pesos e treino não constam do repositório | Impossível auditar/retreinar a rede neural neste projeto | Limite de evidências |

Nenhuma observação acima constitui medição de alucinação, qualidade ou velocidade do modelo em produção.

## Primeira intervenção controlada

Foi criado o módulo `server/cognitive_math.py`: verificador **restrito** de expressão aritmética isolada.

- Parser AST de lista permitida: números, sinais, +, -, *, /, potências inteiras limitadas e parênteses.
- `Fraction` e `Decimal` evitam erro de ponto flutuante em operações decimais exatas.
- Limites de profundidade, tamanho e magnitude para restringir custo; nenhuma execução de código.
- O endpoint autenticado `POST /chat` tenta verificar antes da chamada externa **apenas** expressões reconhecidas integralmente.
- Sem correspondência, utiliza a integração LLM anterior. Para divisão por zero, responde diretamente com uma explicação.
- Quando houver cálculo local, `model=thigas-arithmetic-verifier-v1`, `finish_reason=verified`, com contadores `usage` nulos — não são tokens medidos.
- Não altera prompts, pesos, custo/configuração dos provedores, autenticação nem arquivos de checkpoint.

**Hipótese:** em expressões aritméticas simples e inequívocas, respostas calculadas e verificadas podem evitar erros do modelo externo. O resultado é específico dessa classe; **não implica aumento generalizado do raciocínio da LLM**.

## Suíte PT-BR e linha de base

`eval/train.jsonl`: 15 casos; `eval/val.jsonl`: 8; `eval/test.jsonl`: 15. IDs e enunciados distintos entre conjuntos. Cobertura preliminar: matemática, lógica, interpretação, programação, instruções, incerteza e contexto.

O avaliador `scripts/evaluate_cognition.py` permite validação offline, pontuação de respostas reais já salvas e consulta ao gateway local/remoto, **somente após** `--live --allow-provider-costs`. Não existe inferência automática na execução de testes.

```sh
python scripts/evaluate_cognition.py
python -m unittest discover -s server/tests -v
node --test server/tests/*.test.cjs

# Benchmark com respostas já coletadas (JSONL com id e answer):
python scripts/evaluate_cognition.py --split test --responses resultados_antes.jsonl

# Coletar um baseline usando o gateway autenticado (PODE CONSUMIR CRÉDITOS):
# export THIGAS_ACCESS_PASSWORD=...  # use secret local, nunca no GitHub
python scripts/evaluate_cognition.py --split test --live --allow-provider-costs \
  --url http://127.0.0.1:7860 --output baseline_test.jsonl
```

**Situação inicial:** nenhum baseline da API real foi medido nesta auditoria; acurácia, latência, tokens/s e memória **não disponíveis** até uma execução autorizada. O avaliador calcula tokens/s apenas quando houver `completion_tokens` informado pelo provedor e tempo medido. Medição de memória do servidor/modelo continua pendente: RAM do cliente Python não serve como proxy.

Os critérios automáticos (`exact`, `last_number`, `contains_all`, `regex`) são aproximados; validação humana e avaliação funcional de código ainda são necessárias. O conjunto pequeno não comprova generalização. Para estudos comparativos: manter conjunto de teste fechado, registrar versão, modo, modelo reportado, seeds apenas se suportadas, configurações e custo efetivo antes/depois. Não utilizar respostas do teste para SFT.

## Próximas melhorias, condicionadas às evidências

1. Coletar baseline real autorizado e analisar erros por categoria. Meta de +10 pontos percentuais: **aspiração, não resultado**.
2. Melhorar seleção de contexto sem perder fatos importantes; controlar regressões com teste de múltiplos turnos.
3. Construir verificadores independentes de código e problemas matemáticos contextualizados, sem executar código não confiável no servidor de produção.
4. Só após disponibilizar arquitetura, tokenizer, checkpoints e logs de treino da LLM própria: medir parâmetros reais, propor currículo e SFT/LoRA conforme hardware; exportar GGUF apenas se houver conversor compatível.

**Nota de segurança:** não commitar arquivos de respostas que contenham dados reais dos usuários, senhas, cookies ou tokens. Não há chamadas de API paga necessárias para executar os novos testes unitários.
