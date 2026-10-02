package br.com.thigas.coder;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.os.Build;
import android.content.*;
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
    private static final String BASE="https://thiagollipe-thigas-coder.hf.space";
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private volatile HttpURLConnection active;
    private volatile int generation=0;
    private boolean busy=false;
    private JSONArray history=new JSONArray();
    private LinearLayout messages;
    private ScrollView scroll;
    private EditText input;
    private Button send;
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
        LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setBackgroundColor(Color.rgb(247,250,255));
        root.setOnApplyWindowInsetsListener((v,insets)->{
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets b=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.ime());v.setPadding(b.left,b.top,b.right,b.bottom);}
            else v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        LinearLayout header=new LinearLayout(this);header.setGravity(Gravity.CENTER_VERTICAL);header.setPadding(dp(12),dp(8),dp(8),dp(8));header.setBackgroundColor(Color.WHITE);
        header.addView(cat(48));LinearLayout titles=new LinearLayout(this);titles.setOrientation(1);
        TextView title=text("THIGAS Coder",21);title.setTypeface(null,Typeface.BOLD);titles.addView(title);
        status=text("Assistente de programação · online",12);titles.addView(status);header.addView(titles,new LinearLayout.LayoutParams(0,-2,1));
        Button fresh=button("Nova");fresh.setContentDescription("Nova conversa");header.addView(fresh);root.addView(header);
        scroll=new ScrollView(this);scroll.setFillViewport(true);messages=new LinearLayout(this);messages.setOrientation(1);messages.setPadding(dp(16),dp(16),dp(16),dp(16));scroll.addView(messages);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout composer=new LinearLayout(this);composer.setGravity(Gravity.BOTTOM);composer.setPadding(dp(12),dp(8),dp(12),dp(12));composer.setBackgroundColor(Color.WHITE);
        input=new EditText(this);input.setHint("Pergunte ou cole seu código…");input.setTextColor(ink);input.setTextSize(16);input.setMinLines(1);input.setMaxLines(5);input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);input.setBackground(shape(Color.rgb(240,245,252)));input.setPadding(dp(12),dp(10),dp(12),dp(10));composer.addView(input,new LinearLayout.LayoutParams(0,-2,1));
        send=button("Enviar");composer.addView(send);root.addView(composer);
        setContentView(root);root.requestApplyInsets();
        try{history=new JSONArray(getPreferences(0).getString("history","[]"));}catch(JSONException ignored){}
        redraw();send.setOnClickListener(v->{if(busy)stop();else submit();});
        fresh.setOnClickListener(v->new AlertDialog.Builder(this).setMessage("Iniciar uma nova conversa? O histórico atual será removido deste aparelho.").setNegativeButton("Cancelar",null).setPositiveButton("Nova conversa",(a,b)->{stop();history=new JSONArray();save();redraw();}).show());
    }
    private void welcome(){
        LinearLayout intro=new LinearLayout(this);intro.setOrientation(1);intro.setGravity(Gravity.CENTER);intro.setPadding(0,dp(24),0,dp(20));intro.addView(cat(140));
        TextView heading=text("Vamos criar algo?",25);heading.setTypeface(null,Typeface.BOLD);intro.addView(heading);
        TextView sub=text("Escreva, entenda e corrija códigos\ncom o THIGAS.",16);sub.setGravity(Gravity.CENTER);sub.setPadding(0,dp(10),0,dp(18));intro.addView(sub);
        for(String suggestion:new String[]{"Crie uma função Python que some dois números.","Explique let e const em JavaScript.","Como começar um jogo Match-3?"}){Button b=button(suggestion);b.setOnClickListener(v->{input.setText(suggestion);submit();});intro.addView(b,new LinearLayout.LayoutParams(-1,-2));}messages.addView(intro);
    }
    private void redraw(){messages.removeAllViews();if(history.length()==0)welcome();else for(int i=0;i<history.length();i++){JSONObject m=history.optJSONObject(i);if(m!=null)bubble(m.optString("role"),m.optString("content"));}bottom();}
    private void bottom(){scroll.post(()->scroll.fullScroll(View.FOCUS_DOWN));}
    private LinearLayout bubble(String role,String body){
        LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(dp(14),dp(12),dp(14),dp(12));box.setBackground(shape(role.equals("user")?Color.rgb(223,238,255):Color.WHITE));
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
        String question=input.getText().toString().trim();if(question.isEmpty())return;
        if(question.length()>10000){Toast.makeText(this,"Envie um trecho de código menor.",Toast.LENGTH_LONG).show();return;}
        JSONArray previous=new JSONArray();try{for(int i=Math.max(0,history.length()-12);i<history.length();i++){JSONObject old=history.getJSONObject(i);previous.put(new JSONObject().put("role",old.getString("role")).put("content",new JSONArray().put(new JSONObject().put("type","text").put("text",old.getString("content")))));}}catch(JSONException ignored){}
        if(history.length()==0)messages.removeAllViews();append("user",question);bubble("user",question);input.setText("");
        busy=true;send.setText("Parar");status.setText("Consultando THIGAS… pode haver fila de GPU");pending=bubble("assistant","Aguardando resposta…");bottom();final int id=++generation;
        worker.execute(()->{try{String answer=request(question,previous,id);runOnUiThread(()->{if(generation!=id)return;busy=false;send.setText("Enviar");status.setText("Assistente de programação · online");if(pending!=null)render(pending,answer);pending=null;append("assistant",answer);bottom();});}
            catch(Exception ex){runOnUiThread(()->{if(generation!=id)return;busy=false;send.setText("Enviar");status.setText("Não foi possível obter a resposta");if(pending!=null)render(pending,"Falha na consulta. Confira a conexão e a disponibilidade ou cota de GPU do THIGAS online.\n\n"+ex.getMessage());pending=null;});}});
    }
    private HttpURLConnection connect(String path,int id)throws Exception{
        if(generation!=id)throw new IOException("Consulta interrompida");HttpURLConnection c=(HttpURLConnection)new URL(BASE+path).openConnection();c.setConnectTimeout(20000);c.setReadTimeout(65000);c.setRequestProperty("User-Agent","THIGAS-Android/2.0");active=c;return c;
    }
    private String request(String question,JSONArray previous,int id)throws Exception{
        HttpURLConnection post=connect("/gradio_api/call/responder",id);String event;
        try{post.setRequestMethod("POST");post.setDoOutput(true);post.setRequestProperty("Content-Type","application/json");byte[] raw=new JSONObject().put("data",new JSONArray().put(question).put(previous)).toString().getBytes(StandardCharsets.UTF_8);try(OutputStream out=post.getOutputStream()){out.write(raw);}if(post.getResponseCode()!=200)throw new IOException("HTTP "+post.getResponseCode());StringBuilder b=new StringBuilder();try(BufferedReader reader=new BufferedReader(new InputStreamReader(post.getInputStream(),StandardCharsets.UTF_8))){String line;while((line=reader.readLine())!=null)b.append(line);}event=new JSONObject(b.toString()).getString("event_id");}finally{post.disconnect();}
        if(!event.matches("[A-Za-z0-9_-]+"))throw new IOException("Identificador de consulta inválido");
        HttpURLConnection stream=connect("/gradio_api/call/responder/"+event,id);
        try{if(stream.getResponseCode()!=200)throw new IOException("HTTP "+stream.getResponseCode());try(BufferedReader reader=new BufferedReader(new InputStreamReader(stream.getInputStream(),StandardCharsets.UTF_8))){String line,type="";StringBuilder data=new StringBuilder();long deadline=System.currentTimeMillis()+240000;
            while((line=reader.readLine())!=null){if(generation!=id)throw new IOException("Consulta interrompida");if(System.currentTimeMillis()>deadline)throw new IOException("Tempo de espera excedido");
                if(line.startsWith("event:"))type=line.substring(6).trim();else if(line.startsWith("data:"))data.append(line.substring(5).trim());else if(line.isEmpty()){
                    if(type.equals("error"))throw new IOException("O servidor recusou a consulta. Tente pelo site para verificar sua cota.");
                    if(type.equals("complete")){String answer=extract(new JSONArray(data.toString()));if(answer.isEmpty())throw new IOException("Resposta vazia");return answer;}type="";data.setLength(0);
                }
            }}throw new IOException("Conexão encerrada antes da resposta");}finally{stream.disconnect();if(active==stream)active=null;}
    }
    private String extract(JSONArray result){JSONArray chat=result.optJSONArray(0);if(chat==null)return "";for(int i=chat.length()-1;i>=0;i--){JSONObject m=chat.optJSONObject(i);if(m==null||!m.optString("role").equals("assistant"))continue;Object c=m.opt("content");if(c instanceof String)return (String)c;if(c instanceof JSONArray){StringBuilder b=new StringBuilder();JSONArray blocks=(JSONArray)c;for(int j=0;j<blocks.length();j++){JSONObject block=blocks.optJSONObject(j);if(block!=null&&block.optString("type").equals("text"))b.append(block.optString("text"));}return b.toString();}}return "";}
    @Override protected void onDestroy(){stop();worker.shutdownNow();super.onDestroy();}
}
