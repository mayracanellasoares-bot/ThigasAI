import os
import sqlite3
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch, Mock
from flask import Flask
from docx import Document
import document_agent
from web_workspace import install


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = self.tmp.name+'/accounts.sqlite3'
        env = {'THIGAS_PUBLIC_URL':'https://test.example','THIGAS_SESSION_SECRET':'a'*48,
               'THIGAS_ACCOUNTS_DB':self.path,'GITHUB_CLIENT_ID':'client','GITHUB_CLIENT_SECRET':'secret'}
        self.env = patch.dict(os.environ,env)
        self.env.start(); self.addCleanup(self.env.stop)
        self.app = Flask(__name__); self.app.config['TESTING']=True
        self.compose = Mock(return_value='# Documento\nConteúdo revisado.')
        self.store = document_agent.Store(self.tmp.name+'/files')
        class GatewayError(Exception): pass
        self.gateway = dict(document_store=self.store, compose_reviewed_document=self.compose,
                            extract_document_text=Mock(return_value=('Fonte real',False)),
                            ask_maritaca=Mock(),GatewayError=GatewayError)
        install(self.app,self.gateway)
        self.client = self.app.test_client()
        self.client.get('/auth/me',base_url='https://test.example')
        self.login('one')

    def login(self,uid):
        # /auth/me opens the same schema used by real callback.
        with self.client.session_transaction(base_url='https://test.example') as session:
            session['uid']=uid; session['csrf']='csrf'
        self.client.get('/auth/me',base_url='https://test.example')
        with sqlite3.connect(self.path) as con:
            con.execute('INSERT OR IGNORE INTO users VALUES (?,?,?,?)',(uid,'github',uid,uid))

    def post(self,path,**kwargs):
        return self.client.post(path,base_url='https://test.example',headers={'X-CSRF-Token':'csrf'},**kwargs)

    def test_guest_and_csrf_are_rejected(self):
        guest=self.app.test_client()
        self.assertEqual(guest.post('/workspace/api/generate',json={}).status_code,401)
        self.assertEqual(self.client.post('/workspace/api/clear',base_url='https://test.example').status_code,403)
        self.assertEqual(self.client.get('/auth/me',base_url='https://test.example').headers['Cache-Control'],'no-store')

    def test_generate_preview_approve_and_download_isolated(self):
        response=self.post('/workspace/api/generate',json={'instruction':'Crie uma aula','format':'docx'})
        self.assertEqual(response.status_code,200)
        pid=response.json['id'];url='/workspace/api/download/'+pid
        self.assertEqual(self.client.get(url,base_url='https://test.example').status_code,404)
        self.assertEqual(self.post('/workspace/api/decision/'+pid,json={'approve':True}).status_code,200)
        downloaded=self.client.get(url,base_url='https://test.example')
        self.assertEqual(downloaded.status_code,200)
        self.assertIn('Conteúdo revisado.', [p.text for p in Document(BytesIO(downloaded.data)).paragraphs])
        self.login('two')
        self.assertEqual(self.client.get(url,base_url='https://test.example').status_code,404)
        self.assertEqual(self.post('/workspace/api/decision/'+pid,json={'approve':True}).status_code,409)

    def test_source_is_sent_and_clear_removes_source(self):
        response=self.post('/workspace/api/upload',data={'file':(BytesIO(b'fixture'),'source.pdf')})
        self.assertEqual(response.status_code,200)
        self.post('/workspace/api/generate',json={'instruction':'Resuma','format':'pdf','use_attachment':True})
        self.compose.assert_called_once_with('Resuma','Fonte real')
        self.post('/workspace/api/clear',json={})
        self.assertIsNone(self.store.attached('web:one'))

    def test_cancel_and_invalid_payload(self):
        pid=self.store.propose('web:one','test.pdf',b'pdf')
        self.assertEqual(self.post('/workspace/api/decision/'+pid,json={'approve':'yes'}).status_code,400)
        self.assertEqual(self.post('/workspace/api/decision/'+pid,json={'approve':False}).status_code,200)
        self.assertIsNone(self.store.approved(pid,'web:one'))
        self.assertEqual(self.post('/workspace/api/generate',json=[]).status_code,400)

    def test_real_oauth_redirect_uses_state_and_pkce_and_rejects_bad_callback(self):
        response=self.client.get('/auth/login/github',base_url='https://test.example')
        self.assertEqual(response.status_code,302)
        self.assertIn('state=',response.location)
        self.assertIn('code_challenge=',response.location)
        self.assertEqual(self.client.get('/auth/callback/github?code=bad&state=bad',base_url='https://test.example').status_code,400)

    def test_oauth_callback_creates_stable_account_without_storing_token(self):
        client=self.app.extensions['authlib.integrations.flask_client'].create_client('github')
        profile=Mock();profile.json.return_value={'id':77,'name':'Thiago'}
        with patch.object(client,'authorize_access_token',return_value={'access_token':'PRIVATE'}),patch.object(client,'get',return_value=profile):
            response=self.client.get('/auth/callback/github',base_url='https://test.example')
            self.assertEqual(response.status_code,302)
            first=self.client.get('/auth/me',base_url='https://test.example').json
            self.client.get('/auth/callback/github',base_url='https://test.example')
            second=self.client.get('/auth/me',base_url='https://test.example').json
            self.assertEqual(first['user']['id'],second['user']['id'])
            with self.client.session_transaction(base_url='https://test.example') as session:
                self.assertNotIn('PRIVATE',str(dict(session)))

    def test_delete_account_removes_files_and_invalidates_session(self):
        self.store.attach('web:one','x.pdf',b'x')
        self.assertEqual(self.post('/workspace/api/delete-account',json={}).status_code,200)
        self.assertIsNone(self.store.attached('web:one'))
        self.assertIsNone(self.client.get('/auth/me',base_url='https://test.example').json['user'])

    def test_quota_checked_before_model(self):
        for i in range(20): self.store.propose('web:one','x.pdf',b'x')
        self.assertEqual(self.post('/workspace/api/generate',json={'instruction':'Teste','format':'pdf'}).status_code,429)
        self.compose.assert_not_called()

    def test_xlsx_review_and_expired_source(self):
        from openpyxl import Workbook, load_workbook
        book=Workbook(); book.active.title='Aula'; book.active['A1']='Antes'
        output=BytesIO(); book.save(output); book.close()
        self.assertEqual(self.post('/workspace/api/upload',data={'file':(BytesIO(output.getvalue()),'aula.xlsx')}).status_code,200)
        self.gateway['ask_maritaca'].return_value='{"edits":[{"sheet":"Aula","cell":"A1","value":"Depois"}]}'
        result=self.post('/workspace/api/generate',json={'instruction':'Atualize A1','format':'xlsx','use_attachment':True})
        self.assertEqual(result.status_code,200)
        pid=result.json['id']; self.post('/workspace/api/decision/'+pid,json={'approve':True})
        data=self.client.get('/workspace/api/download/'+pid,base_url='https://test.example').data
        book=load_workbook(BytesIO(data)); self.assertEqual(book.active['A1'].value,'Depois');book.close()
        self.store.clear('web:one')
        result=self.post('/workspace/api/generate',json={'instruction':'Use a fonte','format':'docx','use_attachment':True})
        self.assertEqual(result.status_code,400)

    def test_chat_requires_login_when_provider_configured(self):
        self.assertEqual(self.app.test_client().post('/chat').status_code,401)
        self.assertEqual(self.client.post('/chat',base_url='https://test.example').status_code,403)
        self.assertEqual(self.client.post('/chat',base_url='https://test.example',headers={'Origin':'https://test.example'}).status_code,404)
