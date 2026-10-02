package br.com.thigas.coder;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.os.Build;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.regex.*;

public class MainActivity extends Activity {
    private static final String BASE="https://thigas-coder-gateway.onrender.com";
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private volatile HttpURLConnection active;
    private volatile int generation=0;
    private boolean busy=false;
    private JSONArray history=new JSONArray();
    private LinearLayout messages;
    private ScrollView scroll;
    private EditText input;
    private Button send;
    private Button attach;
    private TextView fileLabel;
    private String attachedName="";
    private String attachedText="";
    private static final int PICK_FILE=401;
    private static final int MAX_ATTACHMENT_CHARS=60000;
    private TextView status;
    private LinearLayout pending;
    private final int ink=Color.rgb(27,43,67), blue=Color.rgb(35,107,216);

    private int dp(int x){return (int)(getResources().getDisplayMetrics().density*x+.5f);}
    private GradientDrawable shape(int color){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(18));return d;}
    private TextView text(String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(ink);return t;}
    private Button button(String label){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextColor(blue);return b;}
    private ImageView cat(int size){ImageView i=new ImageView(this);i.setImageResource(R.drawable.mascote);i.setContentDescription("Mascote THIGAS: gatinho robô");i.setLayoutParams(new LinearLayout.LayoutParams(dp(size),dp(size)));i.setScaleType(ImageView.ScaleType.FIT_CENTER);return i;}

    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        getWindow().setStatusBarColor(Color.WHITE);getWindow().setNavigationBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(247,250,255));
        root.setOnApplyWindowInsetsListener((v,insets)->{
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets b=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.ime());v.setPadding(b.left,b.top,b.right,b.bottom);}
            else v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        LinearLayout header=new LinearLayout(this);header.setGravity(Gravity.CENTER_VERTICAL);header.setPadding(dp(12),dp(8),dp(8),dp(8));header.setBackgroundColor(Color.WHITE);
        header.addView(cat(48));LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);
        TextView title=text("THIGAS Coder",21);title.setTypeface(null,Typeface.BOLD);titles.addView(title);
        status=text("Assistente de programação · online",12);titles.addView(status);header.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
        Button fresh=button("Nova");fresh.setContentDescription("Nova conversa");header.addView(fresh);root.addView(header);
        scroll=new ScrollView(this);scroll.setFillViewport(true);messages=new LinearLayout(this);messages.setOrientation(LinearLayout.VERTICAL);messages.setPadding(dp(16),dp(16),dp(16),dp(16));scroll.addView(messages);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout composer=new LinearLayout(this);
        composer.setOrientation(LinearLayout.VERTICAL);
        composer.setPadding(dp(12),dp(6),dp(12),dp(12));
        composer.setBackgroundColor(Color.WHITE);
        fileLabel=text("",13);
        fileLabel.setTextColor(blue);
        fileLabel.setVisibility(View.GONE);
        fileLabel.setPadding(dp(8),0,dp(8),dp(6));
        composer.addView(fileLabel,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout composerRow=new LinearLayout(this);
        composerRow.setGravity(Gravity.BOTTOM);
        attach=button("📎");
        attach.setTextSize(19);
        attach.setContentDescription("Anexar arquivo");
        attach.setMinWidth(dp(46));
        attach.setPadding(0,0,0,0);
        composerRow.addView(attach,new LinearLayout.LayoutParams(dp(48),dp(52)));
        input=new EditText(this);
        input.setHint("Pergunte ou cole seu código…");
        input.setTextColor(ink);
        input.setTextSize(16);
        input.setMinLines(1);
        input.setMaxLines(5);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        input.setBackground(shape(Color.rgb(240,245,252)));
        input.setPadding(dp(12),dp(10),dp(12),dp(10));
        composerRow.addView(input,new LinearLayout.LayoutParams(0,-2,1));
        send=button("Enviar");
        composerRow.addView(send);
        composer.addView(composerRow,new LinearLayout.LayoutParams(-1,-2));
        root.addView(composer);
        setContentView(root);root.requestApplyInsets();
        try{history=new JSONArray(getPreferences(0).getString("history","[]"));}catch(JSONException ignored){}
        redraw();send.setOnClickListener(v->{if(busy)stop();else submit();});attach.setOnClickListener(v->pickFile());
        fresh.setOnClickListener(v->new AlertDialog.Builder(this).setMessage("Iniciar uma nova conversa? O histórico atual será removido deste aparelho.").setNegativeButton("Cancelar",null).setPositiveButton("Nova conversa",(a,b)->{stop();history=new JSONArray();save();redraw();}).show());
    }
    private void welcome(){
        LinearLayout intro=new LinearLayout(this);
        intro.setOrientation(LinearLayout.VERTICAL);
        intro.setGravity(Gravity.CENTER);
        intro.setPadding(0,dp(32),0,dp(24));
        intro.addView(cat(128));
        TextView heading=text("Como posso ajudar?",25);
        heading.setTypeface(null,Typeface.BOLD);
        intro.addView(heading);
        TextView sub=text("THIGAS Coder",15);
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0,dp(8),0,0);
        intro.addView(sub);
        messages.addView(intro);
    }
    private void pickFile(){
        Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType("*/*");
        startActivityForResult(picker,PICK_FILE);
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==PICK_FILE && resultCode==RESULT_OK && data!=null && data.getData()!=null){
            loadAttachment(data.getData());
        }
    }
    private void loadAttachment(Uri uri){
        String name=uri.getLastPathSegment();
        Cursor cursor=getContentResolver().query(uri,null,null,null,null);
        if(cursor!=null){
            int column=cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
            if(cursor.moveToFirst() && column>=0)name=cursor.getString(column);
            cursor.close();
        }
        if(name==null || name.trim().isEmpty())name="arquivo";
        try{
            ByteArrayOutputStream out=new ByteArrayOutputStream();
            InputStream in=getContentResolver().openInputStream(uri);
            if(in==null)throw new IOException("Não foi possível abrir o arquivo");
            byte[] buffer=new byte[8192];
            int count;
            int total=0;
            while((count=in.read(buffer))!=-1){
                int remaining=200000-total;
                if(remaining<=0)break;
                int write=Math.min(count,remaining);
                out.write(buffer,0,write);
                total+=write;
                if(write<count)break;
            }
            in.close();
            byte[] raw=out.toByteArray();
            for(int i=0;i<Math.min(raw.length,4096);i++){
                if(raw[i]==0)throw new IOException("Este APK aceita arquivos de texto e código.");
            }
            String content=new String(raw,StandardCharsets.UTF_8).replace("\u0000","");
            if(content.trim().isEmpty())throw new IOException("O arquivo está vazio.");
            if(content.length()>MAX_ATTACHMENT_CHARS){
                content=content.substring(0,MAX_ATTACHMENT_CHARS)+"\n\n[Arquivo truncado para caber na consulta.]";
            }
            attachedName=name;
            attachedText=content;
            fileLabel.setText("📎 "+name);
            fileLabel.setVisibility(View.VISIBLE);
            Toast.makeText(this,"Arquivo anexado",Toast.LENGTH_SHORT).show();
        }catch(Exception ex){
            clearAttachment();
            Toast.makeText(this,ex.getMessage()==null?"Não foi possível anexar o arquivo":ex.getMessage(),Toast.LENGTH_LONG).show();
        }
    }
    private void clearAttachment(){
        attachedName="";
        attachedText="";
        if(fileLabel!=null){
            fileLabel.setText("");
            fileLabel.setVisibility(View.GONE);
        }
    }
    private void redraw(){messages.removeAllViews();if(history.length()==0)welcome();else for(int i=0;i<history.length();i++){JSONObject m=history.optJSONObject(i);if(m!=null)bubble(m.optString("role"),m.optString("content"));}bottom();}
    private void bottom(){scroll.post(()->scroll.fullScroll(View.FOCUS_DOWN));}
    private LinearLayout bubble(String role,String body){
        LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(dp(14),dp(12),dp(14),dp(12));box.setBackground(shape(role.equals("user")?Color.rgb(223,238,255):Color.WHITE));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(12);box.setLayoutParams(lp);messages.addView(box);
        LinearLayout label=new LinearLayout(this);label.setGravity(Gravity.CENTER_VERTICAL);if(!role.equals("user"))label.addView(cat(28));TextView who=text(role.equals("user")?"Você":"THIGAS",12);who.setTypeface(null,Typeface.BOLD);label.addView(who);box.addView(label);render(box,body);return box;
    }
    private void render(LinearLayout box,String body){
        while(box.getChildCount()>1)box.removeViewAt(1);
        Pattern fence=Pattern.compile("```([^\\n]*)\\n([\\s\\S]*?)(?:```|$)");Matcher matcher=fence.matcher(body);int end=0;
        while(matcher.find()){if(matcher.start()>end)addText(box,body.substring(end,matcher.start()));
            String code=matcher.group(2);TextView lang=text(matcher.group(1).trim().isEmpty()?"Código":matcher.group(1).trim(),12);box.addView(lang);
            HorizontalScrollView horizontal=new HorizontalScrollView(this);TextView codeView=text(code,14);codeView.setTypeface(Typeface.MONOSPACE);codeView.setTextIsSelectable(true);codeView.setPadding(dp(10),dp(10),dp(10),dp(10));codeView.setBackground(shape(Color.rgb(239,244,251)));horizontal.addView(codeView);box.addView(horizontal);
            Button copy=button("Copiar código");copy.setOnClickListener(v->copy(code));box.addView(copy);end=matcher.end();}
        if(end<body.length())addText(box,body.substring(end));
        if(!body.isEmpty()){Button copyAll=button("Copiar mensagem");copyAll.setOnClickListener(v->copy(body));box.addView(copyAll);}
    }
    private void addText(LinearLayout box,String s){if(s.trim().isEmpty())return;TextView t=text(s.trim(),16);t.setTextIsSelectable(true);t.setPadding(0,dp(8),0,dp(4));t.setLineSpacing(dp(3),1);box.addView(t);}
    private void copy(String s){((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("THIGAS",s));Toast.makeText(this,"Copiado",Toast.LENGTH_SHORT).show();}
    private void save(){getPreferences(0).edit().putString("history",history.toString()).apply();}
    private void append(String role,String content){try{history.put(new JSONObject().put("role",role).put("content",content));}catch(JSONException ignored){}save();}
    private void stop(){generation++;HttpURLConnection c=active;if(c!=null)c.disconnect();busy=false;send.setText("Enviar");status.setText("Assistente de programação · online");if(pending!=null){messages.removeView(pending);pending=null;}}
    private void submit(){
        String typed=input.getText().toString().trim();
        boolean hasAttachment=!attachedText.isEmpty();
        if(typed.isEmpty() && !hasAttachment)return;
        if(typed.length()>20000){
            Toast.makeText(this,"Envie uma pergunta menor.",Toast.LENGTH_LONG).show();
            return;
        }
        String requestQuestion=typed;
        String visibleQuestion=typed;
        if(hasAttachment){
            String instruction=typed.isEmpty()?"Analise o arquivo anexado e explique o que ele faz.":typed;
            requestQuestion=instruction+"\n\n[Arquivo anexado: "+attachedName+"]\n[Início do arquivo]\n"+attachedText+"\n[Fim do arquivo]";
            visibleQuestion=typed.isEmpty()?"📎 "+attachedName:"📎 "+attachedName+"\n\n"+typed;
        }
        final String requestForServer=requestQuestion;
        JSONArray previous=new JSONArray();
        try{
            for(int i=Math.max(0,history.length()-12);i<history.length();i++){
                JSONObject old=history.getJSONObject(i);
                previous.put(new JSONObject().put("role",old.getString("role")).put("content",new JSONArray().put(new JSONObject().put("type","text").put("text",old.getString("content")))));
            }
        }catch(JSONException ignored){}
        if(history.length()==0)messages.removeAllViews();
        append("user",visibleQuestion);
        bubble("user",visibleQuestion);
        input.setText("");
        clearAttachment();
        busy=true;
        send.setText("Parar");
        status.setText("Consultando THIGAS online…");
        pending=bubble("assistant","Aguardando resposta…");
        bottom();
        final int id=++generation;
        worker.execute(()->{
            try{
                String answer=request(requestForServer,previous,id);
                runOnUiThread(()->{
                    if(generation!=id)return;
                    busy=false;
                    send.setText("Enviar");
                    status.setText("Assistente de programação · online");
                    if(pending!=null)render(pending,answer);
                    pending=null;
                    append("assistant",answer);
                    bottom();
                });
            }catch(Exception ex){
                runOnUiThread(()->{
                    if(generation!=id)return;
                    busy=false;
                    send.setText("Enviar");
                    status.setText("Não foi possível obter a resposta");
                    if(pending!=null)render(pending,"Falha na consulta. Confira a conexão e a disponibilidade do THIGAS online.\\n\\n"+ex.getMessage());
                    pending=null;
                });
            }
        });
    }
    private HttpURLConnection connect(String path,int id)throws Exception{
        if(generation!=id)throw new IOException("Consulta interrompida");HttpURLConnection c=(HttpURLConnection)new URL(BASE+path).openConnection();c.setConnectTimeout(20000);c.setReadTimeout(180000);c.setRequestProperty("User-Agent","THIGAS-Android/2.0");active=c;return c;
    }
    private String request(String question,JSONArray previous,int id)throws Exception{
        HttpURLConnection connection=connect("/chat",id);
        try{
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type","application/json; charset=UTF-8");
            connection.setRequestProperty("Accept","application/json");
            JSONObject payload=new JSONObject()
                .put("message",question)
                .put("history",previous);
            byte[] raw=payload.toString().getBytes(StandardCharsets.UTF_8);
            try(OutputStream out=connection.getOutputStream()){out.write(raw);}
            int code=connection.getResponseCode();
            InputStream stream=code>=400?connection.getErrorStream():connection.getInputStream();
            if(stream==null)throw new IOException("Resposta vazia do servidor");
            StringBuilder body=new StringBuilder();
            try(BufferedReader reader=new BufferedReader(new InputStreamReader(stream,StandardCharsets.UTF_8))){
                String line;
                while((line=reader.readLine())!=null)body.append(line);
            }
            JSONObject result;
            try{result=new JSONObject(body.toString());}
            catch(JSONException parse){throw new IOException("Resposta inválida do servidor");}
            if(code<200||code>=300){
                String error=result.optString("error","HTTP "+code);
                throw new IOException(error);
            }
            String answer=result.optString("answer","").trim();
            if(answer.isEmpty())throw new IOException("Resposta vazia do servidor");
            return answer;
        }finally{
            connection.disconnect();
            if(active==connection)active=null;
        }
    }
    private String extract(JSONArray result){JSONArray chat=result.optJSONArray(0);if(chat==null)return "";for(int i=chat.length()-1;i>=0;i--){JSONObject m=chat.optJSONObject(i);if(m==null||!m.optString("role").equals("assistant"))continue;Object c=m.opt("content");if(c instanceof String)return (String)c;if(c instanceof JSONArray){StringBuilder b=new StringBuilder();JSONArray blocks=(JSONArray)c;for(int j=0;j<blocks.length();j++){JSONObject block=blocks.optJSONObject(j);if(block!=null&&block.optString("type").equals("text"))b.append(block.optString("text"));}return b.toString();}}return "";}
    @Override protected void onDestroy(){stop();worker.shutdownNow();super.onDestroy();}
}
