/* battle_host.c: host check of patches 0135, 0137 and 0142: the original formulas of the fight (as in the commit before) against the table-driven ones with the numbers of
 * content/tables/battle-formulas.json (the SLOTS list below is generated from it). gcc -w -I<a dir holding dw/types.h with #include <stdint.h>> -I build/decomp-full/include/dw -o h tools/dev/playtest/battle_host.c && ./h */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_battle.h"
int16_t MOD_BATTLE[MOD_BT_SIZE] = { 30, 30, 500, 500, 10, 90, 21, 100, 101, 41, 40, 1, 3, 10, 999, 2, 999, 120, 165, 10, 21, 3, 6, 8, 20, 41, 42, 34, 21, 30, 30, 10, 0, 7, 25, 0, 5, 20, 8, 15, 0, 10, 10, 7, 15, 100, 1, 3, 200, 101, 200, 41, 3, 50, 700, 800, 900, 999, 5, 10, 15, 20, 100, 100, 1, 155, 100, 40, 80, 301, 70, 300, 4, 100, 2, 20, 4, 3000, 20, 100, 400, 600, 4, 5, 10, 5, 5, 224, 81, 19, 110, 7, 150, 71, 5, 5, 20, 200, 10, 15, 15, 31, 20, 50, 20, 5, 0, 50, 20, 10, 0, 10, 5, 0, 0, 10, 7, 5, 3, 1, 2, 5, 15, 20, 999, 10, 300, 40, 100, 500, 3, 4, 5, 7, 8, 9, 2, 3, 4, 5, 6, 7, 5, 5, 80, 2, 80, 80, 100, 20, 40, 2, 80, 100, 160, 30, 20, 171, 20, 30, 115, 3 };
int32_t modBtBrainDiscount(int32_t brain){ int32_t i,pct=0; for(i=0;i<4;i++) if(MOD_BATTLE[MOD_BT_MP_BRAIN0+i]>=0&&brain>=MOD_BATTLE[MOD_BT_MP_BRAIN0+i]&&MOD_BATTLE[MOD_BT_MP_DISC0+i]>=0) pct=MOD_BATTLE[MOD_BT_MP_DISC0+i]; return pct; }
static int rr;
static int randomLimit(int n){ return rr % n; }
long bad, total;
#define CK(name, a, b) do { total++; if ((a) != (b)) { if (bad++ < 10) printf("DIFF %s: old %ld new %ld at %d\n", name, (long)(a), (long)(b), rr); } } while (0)

static int32_t oldDmg(int atk, int def, int power, int m0, int m1, int m2, int fin, int enemyFin, int charge, int guard) {
	int diff, dmg;
	if (guard) def = def * 3 / 10;
	if (fin) {
		dmg = (atk + power) * (m0 + m1 + m2) / 30;
		if (enemyFin == 0) { if (charge >= 0x29) dmg = dmg * charge / 40; } else dmg = dmg * (randomLimit(0x65) + 0x64) / 100;
		dmg = dmg * (randomLimit(0x15) + 0x5a) / 100;
	} else {
		diff = atk - def;
		if (diff >= 0x1f5) diff = 0x1f4;
		if (diff < -0x1f4) diff = -0x1f4;
		dmg = (m0 + m1 + m2) * (power + diff * power / 500) / 30 * (randomLimit(0x15) + 0x5a) / 100;
	}
	if (dmg <= 0) dmg = 1;
	return dmg;
}
static int32_t newDmg(int atk, int def, int power, int m0, int m1, int m2, int fin, int enemyFin, int charge, int guard) {
	int diff, dmg;
	if (guard) def = def * BM(GUARD_PCT) / 100;
	if (fin) {
		dmg = BMD((atk + power) * (m0 + m1 + m2), DMG_DIV);
		if (enemyFin == 0) { if (charge >= BM(CHARGE_FROM)) dmg = BMD(dmg * charge, CHARGE_DIV); } else dmg = dmg * (randomLimit(BMS(ENEMY_FIN_SPAN)) + BM(ENEMY_FIN_MIN)) / 100;
		dmg = dmg * (randomLimit(BMS(RAND_SPAN)) + BM(RAND_MIN)) / 100;
	} else {
		diff = atk - def;
		if (diff > BM(DIFF_CLAMP)) diff = BM(DIFF_CLAMP);
		if (diff < -BM(DIFF_CLAMP)) diff = -BM(DIFF_CLAMP);
		dmg = BMD((m0 + m1 + m2) * (power + BMD(diff * power, DIFF_DIV)), DMG_DIV) * (randomLimit(BMS(RAND_SPAN)) + BM(RAND_MIN)) / 100;
	}
	if (dmg <= BM(DMG_MIN) - 1) dmg = BM(DMG_MIN);
	return dmg;
}
static int oldHit(int acc, int dspd, int aspd, int moving) {
	int sd = dspd - (aspd / 10), x, r;
	if (sd > 999) sd = 999; if (sd < -999) sd = -999;
	x = acc / 2 * sd / 999;
	if (moving) x = x * 6 / 5;
	r = acc - x; if (r < 0) r = 0; if (r > 100) r = 100; return r;
}
static int newHit(int acc, int dspd, int aspd, int moving) {
	int sd = dspd - BMD(aspd, HIT_SPEED_DIV), x, r;
	if (sd > BM(HIT_SPEED_CLAMP)) sd = BM(HIT_SPEED_CLAMP); if (sd < -BM(HIT_SPEED_CLAMP)) sd = -BM(HIT_SPEED_CLAMP);
	x = BMD(BMD(acc, HIT_ACC_DIV) * sd, HIT_SPEED_NORM);
	if (moving) x = x * BM(HIT_MOVING_PCT) / 100;
	r = acc - x; if (r < 0) r = 0; if (r > 100) r = 100; return r;
}
static int oldMp(int cost, int brain, int cond) {
	int mp = cost * 3;
	if (brain >= 700) { if (brain >= 999) mp -= mp / 5; else if (brain >= 900) mp -= mp * 15 / 100; else if (brain >= 800) mp -= mp / 10; else mp -= mp / 20; }
	if (cond) mp += mp / 2; return mp;
}
static int newMp(int cost, int brain, int cond) {
	int mp = cost * BM(MP_MULT);
	mp -= mp * BMBRAIN(brain) / 100;
	if (cond) mp += mp * BM(MP_COND_PCT) / 100; return mp;
}
static int oldSpend(int cost0, int brain, int cond) {
	int cost = cost0 * 3;
	if (cond) cost += cost / 2;
	if (brain >= 0x2bc) { if (brain >= 0x3e7) cost = cost * 4 / 5; else if (brain >= 0x384) cost = cost * 17 / 20; else if (brain >= 0x320) cost = cost * 9 / 10; else cost = cost * 19 / 20; }
	return cost;
}
static int newSpend(int cost0, int brain, int cond) {
	int cost = cost0 * BM(MP_MULT);
	if (cond) cost += cost * BM(MP_COND_PCT) / 100;
	cost = cost * (100 - BMBRAIN(brain)) / 100; return cost;
}
static void oldBuff(int anim, int o, int d, int s, int *r) {
	switch (anim) {
	case 0x29: r[0] = o * 3 / 10; r[1] = 0; r[2] = 0; break;
	case 0x2a: r[0] = o / 10; r[1] = d * 5 / 100; r[2] = s / 10; break;
	case 0x22: r[0] = 0; r[1] = d / 5; r[2] = s / 10; break;
	case 0x15: r[0] = o * 7 / 100; r[1] = d * 8 / 100; r[2] = s * 7 / 100; break;
	case 0x1e: r[0] = o / 4; r[1] = d * 3 / 20; r[2] = s * 3 / 20; break;
	default: r[0] = r[1] = r[2] = -1;
	}
}
static void newBuff(int anim, int o, int d, int s, int *r) {
	int row; r[0] = r[1] = r[2] = 0;
	for (row = 0; row < 5; row++) if (BMV(BUFF_MOVE0 + row) == anim) break;
	if (row == 5) { r[0] = r[1] = r[2] = -1; return; }
	if (BM(BUFF_OFF0 + row) > 0) r[0] = o * BM(BUFF_OFF0 + row) / 100;
	if (BM(BUFF_DEF0 + row) > 0) r[1] = d * BM(BUFF_DEF0 + row) / 100;
	if (BM(BUFF_SPD0 + row) > 0) r[2] = s * BM(BUFF_SPD0 + row) / 100;
}

/* patch 0137: the AI weights, element bonus, target score, command menus and the post-fight heal, the old literals against the table */
static int oldElem(int f) { switch (f) { case 20: return 10; case 15: return 7; case 10: return 5; case 5: return 3; case 2: return 1; } return 0; }
static int newElem(int f) { switch (f) { case 20: return BM(ELEM0); case 15: return BM(ELEM1); case 10: return BM(ELEM2); case 5: return BM(ELEM3); case 2: return BM(ELEM4); } return 0; }
static int oldTscore(int hp, int maxhp, int def, int f) {
	int mult = f;
	switch (mult) { case 20: mult = 2; break; case 15: mult = 5; break; case 5: mult = 15; break; case 2: mult = 20; break; }
	return hp * 100 / maxhp + mult * (def * 100 / 999) / 10;
}
static int newTscore(int hp, int maxhp, int def, int f) {
	int mult = f;
	switch (mult) { case 20: mult = BM(TSCORE_INV0); break; case 15: mult = BM(TSCORE_INV1); break; case 5: mult = BM(TSCORE_INV2); break; case 2: mult = BM(TSCORE_INV3); break; }
	return hp * 100 / maxhp + BMD(mult * BMD(def * 100, TSCORE_DEF), TSCORE_DIV);
}
static int oldCmd(int brain, int std) { static const int st[5] = { 3, 4, 5, 7, 8 }, sd[5] = { 2, 3, 4, 5, 6 }; return brain < 0x1f4 ? (std ? sd : st)[brain / 100] : (std ? 7 : 9); }
static int newCmd(int brain, int std) { return std ? modBtCommands(brain, MOD_BT_CMD_STD0, MOD_BT_CMD_STD_TOP) : modBtCommands(brain, MOD_BT_CMD_BTL0, MOD_BT_CMD_BTL_TOP); }
/* the weights BTL_selectPartnerMove gives its three moves before the random pick, modes 1 and 0 with a group move (range 3) and mode 2 below the low-HP mark */
static void oldWeights(int mode, int *usable, int *empty, int *range, int brain, int count, int hppct, int *prio, int *w) {
	int i; for (i = 0; i < 3; i++) w[i] = 0;
	if (mode == 1) for (i = 0; i < 3; i++) { if (empty[i]) w[i] += 5; if (usable[i]) w[i] += 0x14; }
	else for (i = 0; i < 3; i++) if (empty[i]) w[i] += 5; else if (usable[i]) w[i] = prio[i];
	for (i = 0; i < 3; i++) {
		if (empty[i]) continue; if (!usable[i]) { w[i] = 0; continue; }
		if (range[i] != 3) continue;
		if (mode == 0 && brain >= 0xc8 && count >= 2) w[i] += count * 10;
		if (mode == 1 && brain >= 0xc8 && count >= 2) w[i] += count * 15;
		if (mode == 2 && brain >= 0xc8 && count >= 2) w[i] += count * 15; else if (mode == 2 && hppct < 0x1f) w[i] += 1000;
	}
}
static void newWeights(int mode, int *usable, int *empty, int *range, int brain, int count, int hppct, int *prio, int *w) {
	int i; for (i = 0; i < 3; i++) w[i] = 0;
	if (mode == 1) for (i = 0; i < 3; i++) { if (empty[i]) w[i] += BM(AI_EMPTY_WEIGHT); if (usable[i]) w[i] += BM(AI_MODE1_WEIGHT); }
	else for (i = 0; i < 3; i++) if (empty[i]) w[i] += BM(AI_EMPTY_WEIGHT); else if (usable[i]) w[i] = prio[i];
	for (i = 0; i < 3; i++) {
		if (empty[i]) continue; if (!usable[i]) { w[i] = 0; continue; }
		if (range[i] != 3) continue;
		if (mode == 0 && brain >= BM(AI_GROUP_BRAIN) && count >= 2) w[i] += count * BM(AI_GROUP_BONUS0);
		if (mode == 1 && brain >= BM(AI_GROUP_BRAIN) && count >= 2) w[i] += count * BM(AI_GROUP_BONUS1);
		if (mode == 2 && brain >= BM(AI_GROUP_BRAIN) && count >= 2) w[i] += count * BM(AI_GROUP_BONUS2); else if (mode == 2 && hppct < BM(AI_LOWHP_PCT)) w[i] += 1000;
	}
}
int main(void) {
	int a, d, p, i, brain, c, mv, anims[6] = { 0x29, 0x2a, 0x22, 0x15, 0x1e, 0x30 };
	for (rr = 0; rr < 400; rr++)
		for (a = 0; a < 10000; a += 331)
			for (d = 0; d < 10000; d += 477)
				for (p = 0; p < 80; p += 7) {
					int m0 = 5 + rr % 11, m1 = 10, m2 = 20 - rr % 7, fin = rr & 1, ef = (rr >> 1) & 1, ch = rr % 90, g = (rr >> 2) & 1;
					CK("damage", oldDmg(a, d, p, m0, m1, m2, fin, ef, ch, g), newDmg(a, d, p, m0, m1, m2, fin, ef, ch, g));
				}
	for (a = 0; a <= 100; a += 5) for (d = 0; d < 1200; d += 11) for (i = 0; i < 1200; i += 13) for (c = 0; c < 2; c++)
		CK("hit", oldHit(a, d, i, c), newHit(a, d, i, c));
	for (brain = 0; brain < 10000; brain++) for (i = 0; i < 40; i += 3) for (c = 0; c < 2; c++) {
		CK("mpUsable", oldMp(i, brain, c), newMp(i, brain, c));
		CK("mpSpend", oldSpend(i, brain, c), newSpend(i, brain, c));
	}
	for (mv = 0; mv < 6; mv++) for (a = 0; a < 3000; a += 37) for (d = 0; d < 3000; d += 61) {
		int r1[3], r2[3]; oldBuff(anims[mv], a, d, a ^ d, r1); newBuff(anims[mv], a, d, a ^ d, r2);
		CK("buff0", r1[0], r2[0]); CK("buff1", r1[1], r2[1]); CK("buff2", r1[2], r2[2]);
	}
	{ static const int fs[] = { 20, 15, 10, 5, 2, 0, 1, 30 }; int k;
	  for (k = 0; k < 8; k++) { CK("element", oldElem(fs[k]), newElem(fs[k])); for (a = 0; a < 3000; a += 7) for (d = 1; d < 1300; d += 11) for (i = 0; i <= 1000; i += 9) CK("targetScore", oldTscore(i, d, a, fs[k]), newTscore(i, d, a, fs[k])); } }
	for (brain = 0; brain < 10000; brain++) for (c = 0; c < 2; c++) CK("commands", oldCmd(brain, c), newCmd(brain, c));
	for (a = 0; a < 40000; a += 7) { CK("healHp", a / 5, BMD(a, HEAL_HP)); CK("healMp", a / 5, BMD(a, HEAL_MP)); }
	{ int m, u, e, rg, cnt, hp, pr[3] = { 50, 20, 5 }, w1[3], w2[3], us[3], em[3], ra[3], x;
	  for (m = 0; m < 3; m++) for (u = 0; u < 27; u++) for (e = 0; e < 27; e++) for (rg = 0; rg < 27; rg++) for (cnt = 0; cnt <= 4; cnt++) for (brain = 0; brain < 600; brain += 25) for (hp = 0; hp <= 100; hp += 10) {
	    for (x = 0; x < 3; x++) { us[x] = (u / (x == 0 ? 1 : x == 1 ? 3 : 9)) % 3 != 0; em[x] = (e / (x == 0 ? 1 : x == 1 ? 3 : 9)) % 3 == 0; ra[x] = 1 + (rg / (x == 0 ? 1 : x == 1 ? 3 : 9)) % 3 + 1; }
	    oldWeights(m, us, em, ra, brain, cnt, hp, pr, w1); newWeights(m, us, em, ra, brain, cnt, hp, pr, w2);
	    for (x = 0; x < 3; x++) CK("partnerWeights", w1[x], w2[x]); } }
	/* patch 0142: the defeat countdown's digit (31, 0x1d + 30, 0x96) and the last-battle music rule */
	{ int t; for (t = 0; t < 400; t++) { CK("countdownStep", t % 31 == 0, t % (BMS(T_DIGIT) + 1) == 0); CK("countdownDigit", (t + 0x1d) / 30, (t + BMS(T_DIGIT) - 1) / BMS(T_DIGIT)); CK("countdownEnd", t >= 0x96, t >= 5 * BMS(T_DIGIT)); }
	  for (t = 0; t < 256; t++) CK("lastBattleMusic", t == 0x73, BMV(MUSIC_LAST_SPECIES) >= 0 && t == BMV(MUSIC_LAST_SPECIES)); CK("lastBattleTrack", 3, BM(MUSIC_LAST_TRACK)); }
	printf("%ld cases, %ld differ\n", total, bad);
	return bad != 0;
}
