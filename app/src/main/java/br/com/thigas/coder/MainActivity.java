package br.com.thigas.coder;

import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.net.Uri;
import android.graphics.Color;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.*;
import android.widget.*;

public class MainActivity extends Activity {
    // URL direta do Space. Se renomear o Space, atualize este endereço.
    private static final String APP_URL = "https://thiagollipe-thigas-coder.hf.space/";
    private WebView web;
    private ProgressBar progress;
    private LinearLayout error;
    private boolean failed;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        TextView title = new TextView(this);
        title.setText("THIGAS Coder"); title.setTextSize(22);
        title.setTextColor(Color.WHITE); title.setBackgroundColor(Color.rgb(20,34,56));
        title.setPadding(24,16,24,16); root.addView(title);
        LinearLayout toolbar = new LinearLayout(this);
        Button reload = new Button(this); reload.setText("Recarregar");
        Button browser = new Button(this); browser.setText("Abrir no navegador");
        toolbar.addView(reload, new LinearLayout.LayoutParams(0, -2, 1));
        toolbar.addView(browser, new LinearLayout.LayoutParams(0, -2, 1)); root.addView(toolbar);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        root.addView(progress, new LinearLayout.LayoutParams(-1, 6));
        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
        web = new WebView(this); content.addView(web, new FrameLayout.LayoutParams(-1,-1));
        error = new LinearLayout(this); error.setOrientation(LinearLayout.VERTICAL);
        error.setPadding(32,32,32,32); error.setBackgroundColor(Color.WHITE);
        TextView notice = new TextView(this);
        notice.setText("Não foi possível abrir o THIGAS. Confira sua conexão e se o Space está funcionando.");
        notice.setTextSize(18); error.addView(notice);
        Button retry = new Button(this); retry.setText("Tentar novamente"); error.addView(retry);
        content.addView(error, new FrameLayout.LayoutParams(-1,-1)); error.setVisibility(View.GONE);
        setContentView(root); root.requestApplyInsets();
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) { progress.setProgress(value); }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                failed = false; error.setVisibility(View.GONE); progress.setVisibility(View.VISIBLE);
            }
            @Override public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
                if (failed) error.setVisibility(View.VISIBLE);
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) showError();
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest req, WebResourceResponse response) {
                if (req.isForMainFrame() && response.getStatusCode() >= 400) showError();
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                if (!req.isForMainFrame()) return false;
                Uri uri = req.getUrl();
                if ("https".equals(uri.getScheme()) && Uri.parse(APP_URL).getHost().equals(uri.getHost())) return false;
                openBrowser(uri); return true;
            }
        });
        web.setDownloadListener((url, agent, disposition, mime, length) -> openBrowser(Uri.parse(url)));
        reload.setOnClickListener(v -> loadHome()); retry.setOnClickListener(v -> loadHome());
        browser.setOnClickListener(v -> openBrowser(Uri.parse(APP_URL)));
        if (state == null || web.restoreState(state) == null) loadHome();
    }
    private void showError() { failed = true; error.setVisibility(View.VISIBLE); progress.setVisibility(View.GONE); }
    private void loadHome() { error.setVisibility(View.GONE); web.loadUrl(APP_URL); }
    private void openBrowser(Uri uri) {
        if (!"https".equals(uri.getScheme()) && !"http".equals(uri.getScheme())) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
        catch (ActivityNotFoundException ex) { Toast.makeText(this, "Nenhum navegador disponível.", Toast.LENGTH_SHORT).show(); }
    }
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onSaveInstanceState(Bundle state) { web.saveState(state); super.onSaveInstanceState(state); }
    @Override protected void onDestroy() { web.stopLoading(); web.destroy(); super.onDestroy(); }
}
