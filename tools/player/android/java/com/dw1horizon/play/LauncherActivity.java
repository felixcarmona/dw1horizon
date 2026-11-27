package com.dw1horizon.play;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * The first screen: takes the patched disc (the .bin the Horizon patcher built) into the app's folder once, puts the
 * OpenBIOS image next to it, and starts HorizonActivity. The folder is the app's external files folder
 * (Android/data/com.dw1horizon.play/files), so the disc and the memory card can also be copied over USB.
 */
public class LauncherActivity extends Activity {
    private static final int PICK = 1;
    private static final int SECTOR = 2352;
    private TextView status;
    private Button play, choose;
    private ProgressBar bar;
    private boolean busy;

    static File dataDir(Context c) {
        File d = c.getExternalFilesDir(null);
        return d != null ? d : c.getFilesDir();
    }

    static File bin(Context c) { return new File(new File(dataDir(c), "disc"), "horizon.bin"); }

    static File cue(Context c) { return new File(new File(dataDir(c), "disc"), "horizon.cue"); }

    /** The cue of a disc the patcher put inside this APK (assets/horizon.bin, stored): its track is read in place. */
    static File embeddedCue(Context c) { return new File(new File(dataDir(c), "disc"), "embedded.cue"); }

    /** {offset, size} of assets/horizon.bin inside the APK, or null when this APK carries no disc. */
    static long[] embedded(Context c) {
        try (android.content.res.AssetFileDescriptor fd = c.getAssets().openFd("horizon.bin")) {
            return new long[] {fd.getStartOffset(), fd.getLength()};
        } catch (java.io.IOException e) {
            return null;
        }
    }

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        int pad = (int) (24 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(0x1b, 0x1a, 0x24));

        TextView title = new TextView(this);
        title.setText(R.string.title);
        title.setTextSize(26);
        title.setTextColor(Color.rgb(0xff, 0xe1, 0xc4));
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        status = new TextView(this);
        status.setTextSize(16);
        status.setTextColor(Color.rgb(0xcf, 0xd8, 0xf6));
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, pad, 0, pad);
        root.addView(status);

        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(1000);
        bar.setVisibility(View.GONE);
        root.addView(bar, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,
                                                        LinearLayout.LayoutParams.WRAP_CONTENT));

        play = new Button(this);
        play.setText(R.string.play);
        play.setTextSize(22);
        play.setOnClickListener(v -> startGame());
        root.addView(play);

        choose = new Button(this);
        choose.setOnClickListener(v -> pick());
        root.addView(choose);

        setContentView(root);
        installBios();
        new File(dataDir(this), "saves").mkdirs();
        if (embedded(this) != null) {   // the patcher's own APK: straight into the game
            try {
                File cue = embeddedCue(this);
                cue.getParentFile().mkdirs();
                try (OutputStream o = new FileOutputStream(cue)) {
                    o.write("FILE \"embedded.bin\" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n".getBytes("US-ASCII"));
                }
                startActivity(new Intent(this, HorizonActivity.class));
                finish();
                return;
            } catch (java.io.IOException e) {
                status.setText(e.toString());
            }
        }
        refresh(null);
        if (haveDisc()) play.requestFocus(); else choose.requestFocus();
    }

    private boolean haveDisc() {
        File b = bin(this);
        return b.length() > 0 && b.length() % SECTOR == 0 && cue(this).exists();
    }

    private void refresh(String message) {
        boolean ok = haveDisc();
        play.setEnabled(ok && !busy);
        choose.setEnabled(!busy);
        choose.setText(ok ? R.string.change : R.string.choose);
        if (message != null) status.setText(message);
        else status.setText(ok ? getString(R.string.ready) + "\n"
                                   + getString(R.string.saves, new File(dataDir(this), "saves").getPath())
                               : getString(R.string.no_disc));
    }

    private void startGame() {
        if (haveDisc()) startActivity(new Intent(this, HorizonActivity.class));
    }

    private void pick() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        startActivityForResult(i, PICK);
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != PICK || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        String name = "";
        long size = -1;
        try (Cursor c = getContentResolver().query(uri, null, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                int n = c.getColumnIndex(OpenableColumns.DISPLAY_NAME), s = c.getColumnIndex(OpenableColumns.SIZE);
                if (n >= 0) name = c.getString(n);
                if (s >= 0 && !c.isNull(s)) size = c.getLong(s);
            }
        } catch (RuntimeException e) {
            // no name or size: checked after the copy
        }
        if (name != null && name.toLowerCase().endsWith(".cue")) { refresh(getString(R.string.pick_bin)); return; }
        if (size >= 0 && (size == 0 || size % SECTOR != 0)) { refresh(getString(R.string.not_a_disc)); return; }
        copy(uri, size);
    }

    private void copy(Uri uri, long size) {
        busy = true;
        bar.setProgress(0);
        bar.setVisibility(View.VISIBLE);
        refresh(getString(R.string.copying));
        new Thread(() -> {
            String error = null;
            File out = bin(this), part = new File(out.getPath() + ".part");
            out.getParentFile().mkdirs();
            try (InputStream in = getContentResolver().openInputStream(uri);
                 OutputStream o = new FileOutputStream(part)) {
                byte[] buf = new byte[1 << 20];
                long done = 0;
                for (int n; (n = in.read(buf)) > 0; ) {
                    o.write(buf, 0, n);
                    done += n;
                    if (size > 0) { final int p = (int) (done * 1000 / size); runOnUiThread(() -> bar.setProgress(p)); }
                }
                o.close();
                if (done == 0 || done % SECTOR != 0) error = getString(R.string.not_a_disc);
                else {
                    try (OutputStream c = new FileOutputStream(cue(this))) {
                        c.write("FILE \"horizon.bin\" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n".getBytes("UTF-8"));
                    }
                    out.delete();
                    if (!part.renameTo(out)) error = "rename";
                }
            } catch (Exception e) {
                error = getString(R.string.copy_failed, String.valueOf(e.getMessage()));
            }
            part.delete();
            final String err = error;
            runOnUiThread(() -> {
                busy = false;
                bar.setVisibility(View.GONE);
                refresh(err);
                if (err == null) { play.requestFocus(); startGame(); }
            });
        }).start();
    }

    /** OpenBIOS ships in the APK's assets; the core reads it from the system folder. */
    private void installBios() {
        File sys = new File(dataDir(this), "system"), bios = new File(sys, "openbios.bin");
        sys.mkdirs();
        try (InputStream in = getAssets().open("openbios.bin")) {
            byte[] data = new byte[in.available() > 0 ? in.available() : 1 << 20];
            int total = 0;
            for (int n; (n = in.read(data, total, data.length - total)) > 0; ) total += n;
            if (bios.length() == total) return;
            try (OutputStream o = new FileOutputStream(bios)) { o.write(data, 0, total); }
        } catch (Exception e) {
            refresh(getString(R.string.copy_failed, "openbios.bin: " + e.getMessage()));
        }
    }
}
