package com.dw1horizon.play;

import java.io.File;
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

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // this activity has its own process: end it, so the next game starts the native side afresh
        android.os.Process.killProcess(android.os.Process.myPid());
    }
}
