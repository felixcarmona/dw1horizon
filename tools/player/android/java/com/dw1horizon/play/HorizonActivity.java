package com.dw1horizon.play;

import android.Manifest;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Scanner;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
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

    // ---- the memory card's copy outside the app (docs/player.md): Android deletes the app's own folder when the app
    // is uninstalled, and an APK signed with another key has to be installed that way. horizon_play.c calls backupCard
    // after each write of the card; a new install offers to import it, the file picker opened at its folder. ----
    static final String BACKUP_DIR = "Digimon World Horizon", BACKUP_NAME = "Digimon World Horizon.mcd";
    private static final Object backupLock = new Object();

    // ---- a newer release (docs/player.md): the latest release's tag on GitHub, when it is newer than this app; the
    // menu shows it (horizon_play.c reads this field). The repository is assets/releases.txt, written by build_apk.py.
    static volatile String newVersion = "";

    private static int[] versionKey(String v) {
        Matcher m = Pattern.compile("^v?(\\d+)\\.(\\d+)\\.(\\d+)").matcher(v == null ? "" : v);
        if (!m.find()) return null;
        return new int[] {Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2)), Integer.parseInt(m.group(3))};
    }

    private void checkVersion() {
        final String mine;
        try {
            mine = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            return;
        }
        new Thread(new Runnable() {
            public void run() {
                try {
                    String repo;
                    try (Scanner s = new Scanner(getAssets().open("releases.txt"), "UTF-8")) {
                        repo = s.hasNextLine() ? s.nextLine().trim() : "";
                    }
                    if (repo.isEmpty()) return;
                    HttpURLConnection c = (HttpURLConnection) new URL(
                        "https://api.github.com/repos/" + repo + "/releases/latest").openConnection();
                    c.setConnectTimeout(10000); c.setReadTimeout(10000);
                    c.setRequestProperty("Accept", "application/vnd.github+json");
                    if (c.getResponseCode() != 200) return;
                    String body;
                    try (Scanner s = new Scanner(c.getInputStream(), "UTF-8")) {
                        body = s.useDelimiter("\\A").hasNext() ? s.next() : "";
                    }
                    Matcher m = Pattern.compile("\"tag_name\"\\s*:\\s*\"([^\"]+)\"").matcher(body);
                    if (!m.find()) return;
                    int[] a = versionKey(m.group(1)), b = versionKey(mine);
                    if (a == null || b == null) return;
                    for (int i = 0; i < 3; i++) {
                        if (a[i] != b[i]) {
                            if (a[i] > b[i]) newVersion = m.group(1);
                            return;
                        }
                    }
                } catch (Exception e) {
                    // offline, or GitHub refused: no notice
                }
            }
        }).start();
    }

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        checkVersion();
        // before Android 10 a file outside the app needs the storage permission: asked once
        if (Build.VERSION.SDK_INT < 29
            && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            SharedPreferences p = getSharedPreferences("horizon", MODE_PRIVATE);
            if (!p.getBoolean("askedStorage", false)) {
                p.edit().putBoolean("askedStorage", true).apply();
                requestPermissions(new String[] {Manifest.permission.WRITE_EXTERNAL_STORAGE}, 43);
            }
        }
    }

    public void backupCard(final String card) {
        new Thread(new Runnable() {
            public void run() {
                synchronized (backupLock) {
                    try {
                        writeBackup(card);
                    } catch (Exception e) {
                        android.util.Log.w("HorizonPlay", "memory card copy: " + e);
                    }
                }
            }
        }).start();
    }

    private void writeBackup(String card) throws java.io.IOException {
        if (Build.VERSION.SDK_INT < 29) {
            if (checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) return;
            File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS), BACKUP_DIR);
            dir.mkdirs();
            File target = new File(dir, BACKUP_NAME);
            SharedPreferences own = getSharedPreferences("horizon", MODE_PRIVATE);
            if (!own.getBoolean("backupOwned", false)) {   // another install's copy: kept aside, not overwritten
                if (target.exists())
                    target.renameTo(new File(dir, "Digimon World Horizon " + System.currentTimeMillis() / 1000 + ".mcd"));
                own.edit().putBoolean("backupOwned", true).apply();
            }
            File tmp = new File(dir, BACKUP_NAME + ".new");
            try (InputStream in = new FileInputStream(card); OutputStream out = new FileOutputStream(tmp)) {
                copy(in, out);
            }
            if (!tmp.renameTo(target)) throw new java.io.IOException("rename");
            return;
        }
        // Android 10 and later: the app's own entry in Documents, kept by its address; a new install makes a new one
        // (Android names it "... (1).mcd" next to the old one)
        SharedPreferences p = getSharedPreferences("horizon", MODE_PRIVATE);
        String known = p.getString("backupUri", null);
        if (known != null) {
            try (InputStream in = new FileInputStream(card);
                 OutputStream out = getContentResolver().openOutputStream(Uri.parse(known), "wt")) {
                copy(in, out);
                return;
            } catch (Exception gone) {
                // deleted by the player: a new one
            }
        }
        ContentValues v = new ContentValues();
        v.put(MediaStore.MediaColumns.DISPLAY_NAME, BACKUP_NAME);
        v.put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream");
        v.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOCUMENTS + "/" + BACKUP_DIR);
        Uri uri = getContentResolver().insert(MediaStore.Files.getContentUri("external"), v);
        if (uri == null) throw new java.io.IOException("no entry in Documents");
        try (InputStream in = new FileInputStream(card); OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
            copy(in, out);
        }
        p.edit().putString("backupUri", uri.toString()).apply();
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
                if (export) i.putExtra(Intent.EXTRA_TITLE, BACKUP_NAME);
                if (Build.VERSION.SDK_INT >= 26)   // the picker opens where the copy is kept (a hint: it may not)
                    i.putExtra(DocumentsContract.EXTRA_INITIAL_URI, DocumentsContract.buildDocumentUri(
                        "com.android.externalstorage.documents", "primary:" + Environment.DIRECTORY_DOCUMENTS + "/" + BACKUP_DIR));
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
