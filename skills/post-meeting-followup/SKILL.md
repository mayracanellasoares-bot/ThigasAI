---
name: post-meeting-followup
description: Preparar uma mensagem de acompanhamento depois de uma reunião
triggers: [google_calendar.meeting_ended]
permissions: [google_calendar.read, gmail.read, gmail.send]
---
# Acompanhamento pós-reunião

Quando uma reunião termina:
1. Leia apenas os detalhes e participantes do evento autorizado.
2. Busque no Gmail o contexto necessário para o assunto, com atenção à privacidade.
3. Proponha uma mensagem objetiva, com decisões e próximos passos confirmados.
4. Se não houver transcrição no evento, não invente falas nem decisões.
5. Crie uma proposta de envio; aguarde aprovação explícita antes de enviar.
