# Correção do esforço alto para programação

Data: 13/10/2026 — THIGAS AI / Brittech.inc

## Falha identificada

No código anterior, `mode=thinking` selecionava uma LLM avançada, mas não configurava `reasoning_effort=high` no GPT-OSS 20B da Groq. Como esse modelo usa `medium` por padrão, o rótulo "Esforço: alto" podia ser enganoso.

O mesmo modo `thinking` pode selecionar o Sabiá 4 Thinking BR-SP, quando `THIGAS_ENABLE_THINKING=true` e `MARITACA_API_KEY` estiver configurada. Esses provedores têm contratos de API diferentes. Não é correto enviar parâmetros exclusivos da Groq ao Sabiá.

Referências oficiais:
- https://console.groq.com/docs/reasoning
- https://console.groq.com/docs/api-reference
- https://docs.maritaca.ai/pt/modelos
- https://docs.maritaca.ai/api/pt/completion

## Alterações

- Para `THIGAS_CLOUD_URL=https://api.groq.com/openai/v1/chat/completions` e `THIGAS_CLOUD_MODEL=openai/gpt-oss-20b` ou `openai/gpt-oss-120b`:
  - `thinking` envia `reasoning_effort=high`;
  - `cloud` envia `reasoning_effort=medium`;
  - `include_reasoning=false` para solicitar somente a resposta final;
  - `max_completion_tokens` substitui `max_tokens` para esse provedor/modelo;
  - `temperature=0.6` e `top_p=0.95` conforme a documentação de inferência da Groq.
- Maritaca continua usando `max_tokens` e suas configurações anteriores, sem parâmetros exclusivos de outro provedor.
- O backend retorna o nome do modelo selecionado e, se aplicável, o `reasoning_effort` efetivamente enviado. O cliente identifica se esforço alto de fato é compatível com o modelo ativo, sem exibir senhas.
- Em solicitações de programação, o prompt técnico solicita checagem de imports, sintaxe, nomes, DOM, eventos, dependências e compatibilidade antes da entrega. **Não é execução/compilação**.
- A análise estática já existente para Python continua ativa; agora também sinaliza JSON inválido.
- Botão **REVISAR CÓDIGO** em respostas com bloco de código prepara um pedido de revisão contextualizado. O usuário deve revisar e clicar Enviar para autorizar nova chamada ao provedor, que pode consumir saldo. Não há segunda chamada automática.

## Limites e segurança

- Passar `reasoning_effort=high` não garante que códigos executem corretamente.
- O aviso de sintaxe não comprova correção lógica; checar código JavaScript/TypeScript completo exigiria ferramentas adequadas de lint/teste em ambiente isolado.
- O código gerado não é executado automaticamente no servidor.
- Os testes automatizados usam mocks para verificar o **payload enviado ao provedor**, e não medem a qualidade do modelo real.
- Para comparar acurácia de programação é necessário um benchmark com testes funcionais em sandbox e inferências reais autorizadas.
- O GPT-OSS pode consumir tokens de raciocínio dentro do orçamento de conclusão, resultando em resposta incompleta se atingir o limite. O THIGAS mantém o limite configurado de 16.384 tokens e informa truncamento quando o provedor reporta `finish_reason=length`.

## Testes sem consumo de API

```bash
python -m unittest discover -s server/tests -v
node --test server/tests/*.test.cjs
```

O resultado deve ser verificado no GitHub Actions antes de publicar em produção. Nenhuma API paga foi usada nessa atualização.
