'use strict';
(() => {
  const el = id => document.getElementById(id);
  let csrf = '', pending = '', busy = false;
  const status = message => { el('status').textContent = message; };
  async function api(path, body, form = false) {
    const options = {cache:'no-store', credentials:'same-origin'};
    if (body !== undefined) {
      options.method = 'POST'; options.headers = {'X-CSRF-Token':csrf};
      if (!form) options.headers['Content-Type'] = 'application/json';
      options.body = form ? body : JSON.stringify(body);
    }
    const response = await fetch(path, options);
    let data; try { data = await response.json(); } catch (_) { data = {}; }
    if (!response.ok) throw new Error(data.error || (response.status === 401 ? 'Entre novamente na sua conta.' : 'Não foi possível concluir. Recarregue a página e tente novamente.'));
    return data;
  }
  async function run(action) {
    if (busy) return;
    busy = true;
    document.querySelectorAll('button').forEach(button => { button.disabled = true; });
    try { await action(); } catch (error) { status(error.message); }
    finally { busy = false; document.querySelectorAll('button').forEach(button => { button.disabled = false; }); }
  }
  async function init() {
    const data = await api('/auth/me'); csrf = data.csrf || '';
    el('tools').hidden = !data.user;
    el('logout').hidden = !data.user; el('delete-account').hidden = !data.user;
    el('identity').textContent = data.user ? 'Conectado como '+data.user.name : 'Entre para criar seu cadastro e usar documentos.';
    el('providers').replaceChildren();
    if (!data.user) {
      const labels = {google:'Entrar com Google',github:'Entrar com GitHub',meta:'Entrar com Facebook (Meta)'};
      for (const provider of data.providers) {
        const link = document.createElement('a'); link.href = '/auth/login/'+provider; link.textContent = labels[provider]; el('providers').append(link);
      }
      if (!data.providers.length) status('O responsável pelo site ainda precisa configurar o login social no servidor.');
    }
  }
  el('upload').onclick = () => run(async () => {
    const file = el('file').files[0];
    if (!file) throw new Error('Selecione um documento.');
    if (file.size > 8*1024*1024) throw new Error('O limite é 8 MB.');
    const form = new FormData(); form.append('file',file); status('Lendo documento…');
    const data = await api('/workspace/api/upload',form,true);
    el('file-status').textContent = data.name; el('source-preview').textContent = data.preview;
    el('use-attachment').disabled = false; el('use-attachment').checked = true;
    status(data.truncated ? 'Arquivo recebido. A extração foi parcial; confira a fonte.' : 'Arquivo recebido.');
  });
  el('generate').onclick = () => run(async () => {
    if (pending) throw new Error('Confirme ou cancele a revisão atual antes de preparar outra.');
    el('download').hidden = true; status('Preparando e revisando. Isso pode levar alguns minutos…');
    const data = await api('/workspace/api/generate',{instruction:el('instruction').value,format:el('format').value,use_attachment:el('use-attachment').checked});
    pending = data.id; el('preview').textContent = data.preview; el('decision').hidden = false; status('Revise o conteúdo antes de confirmar.');
  });
  async function decide(approve) {
    const data = await api('/workspace/api/decision/'+pending,{approve}); pending = ''; el('decision').hidden = true;
    if (data.url) { el('download').href = data.url; el('download').hidden = false; }
    status(approve ? 'Documento liberado. Toque em Baixar documento.' : 'Revisão cancelada.');
  }
  el('approve').onclick = () => run(() => decide(true));
  el('cancel').onclick = () => run(() => decide(false));
  el('logout').onclick = () => run(async () => { await api('/workspace/api/logout',{}); location.reload(); });
  el('delete-account').onclick = () => run(async () => {
    if (!confirm('Excluir seu cadastro e todos os documentos temporários desta conta?')) return;
    await api('/workspace/api/delete-account',{}); location.reload();
  });
  el('clear').onclick = () => run(async () => {
    if (!confirm('Apagar os arquivos e revisões temporários desta conta?')) return;
    await api('/workspace/api/clear',{}); location.reload();
  });
  init().catch(error => status(error.message));
})();
