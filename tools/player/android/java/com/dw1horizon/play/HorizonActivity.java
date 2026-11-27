package com.dw1horizon.play;

import android.content.Intent;
import android.net.Uri;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import org.libsdl.app.SDLActivity;

/** The game: SDL runs horizon_play.c (libmain.so) on the disc LauncherActivity copied (docs/player.md). */
public class HorizonActivity extends SDLActivity {
    @Override
    protected String[] getLibraries() {
        return new String[] {"SDL2", "main"};
    }

    @Override
    protected String[] getArguments() {
        File d = LauncherActivity.dataDir(this);
        long[] e = LauncherActivity.embedded(this);
        if (e != null)
            return new String[] {"--system", new File(d, "system").getPath(), "--saves", new File(d, "saves").getPath(),
                                 "--embedded", getApplicationInfo().sourceDir, Long.toString(e[0]), Long.toString(e[1]),
                                 LauncherActivity.embeddedCue(this).getPath()};
        return new String[] {"--system", new File(d, "system").getPath(), "--saves", new File(d, "saves").getPath(),
                             LauncherActivity.cue(this).getPath()};
    }

    // ---- the menu's memory card export and import (horizon_play.c calls pickCard and reads cardResult) ----
    private static final int EXPORT = 41, IMPORT = 42;
    static volatile int cardResult;   // 0 waiting, 1 done, 2 failed, 3 cancelled
    private String cardFile, importFile;

    public void pickCard(final boolean export, String card, String importTo) {
        cardFile = card;
        importFile = importTo;
        cardResult = 0;
        runOnUiThread(new Runnable() {
            public void run() {
                Intent i = new Intent(export ? Intent.ACTION_CREATE_DOCUMENT : Intent.ACTION_OPEN_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType(export ? "application/octet-stream" : "*/*");
                if (export) i.putExtra(Intent.EXTRA_TITLE, "Digimon World Horizon.mcd");
                try {
                    startActivityForResult(i, export ? EXPORT : IMPORT);
                } catch (Exception e) {
                    cardResult = 2;
                }
            }
        });
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != EXPORT && request != IMPORT) return;
        if (result != RESULT_OK || data == null || data.getData() == null) {
            cardResult = 3;
            return;
        }
        final Uri uri = data.getData();
        final boolean export = request == EXPORT;
        new Thread(new Runnable() {
            public void run() {
                try {
                    if (export) {
                        try (InputStream in = new FileInputStream(cardFile);
                             OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
                            copy(in, out);
                        }
                    } else {
                        File tmp = new File(importFile + ".new");
                        try (InputStream in = getContentResolver().openInputStream(uri);
                             OutputStream out = new FileOutputStream(tmp)) {
                            copy(in, out);
                        }
                        if (!tmp.renameTo(new File(importFile))) throw new java.io.IOException("rename");
                    }
                    cardResult = 1;
                } catch (Exception e) {
                    cardResult = 2;
                }
            }
        }).start();
    }

    private static void copy(InputStream in, OutputStream out) throws java.io.IOException {
        if (in == null || out == null) throw new java.io.IOException("no stream");
        byte[] b = new byte[65536];
        int n, total = 0;
        while ((n = in.read(b)) > 0 && total < (1 << 20)) {   // a memory card is 128 KB: a huge file is not one
            out.write(b, 0, n);
            total += n;
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // this activity has its own process: end it, so the next game starts the native side afresh
        android.os.Process.killProcess(android.os.Process.myPid());
    }
}
