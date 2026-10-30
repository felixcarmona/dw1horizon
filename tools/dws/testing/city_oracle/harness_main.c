/* Driver of the city-rules equivalence harness (tools/dws/testing/city_equivalence.py builds and runs it).
 * o_* are the ORIGINAL functions of decomp/src (main branch), t_* the story-state target functions of build/decomp-story-state/src (the
 * table readers of city_rules.c with the call sites as shipped); both are extracted verbatim and compiled here. */
#include <stdio.h>
#include <stdlib.h>
#include "city_host.h"

/* ---- the game state that the rules look at */
uint8_t H_TRIGGERS[20000];
uint8_t H_PSTATS[256];
uint8_t H_SPECIES_RECRUITED[NUM_DIGIMON];
DigimonPara H_PARA[NUM_DIGIMON];
uint8_t *H_CITY_SECTION;
static uint8_t H_DUMMY[16];
uint8_t *MAPHEAD_SCRIPT_PTR = H_DUMMY;
static int H_LIB; /* 0 none, 1 SHOP_REL, 2 DGET_REL (the last overlay a map check loaded) */

int32_t isTriggerSet(uint16_t t) { return t < 20000 ? H_TRIGGERS[t] : 0; }
void setTrigger(uint16_t t) { if (t < 20000) H_TRIGGERS[t] = 1; }
void unsetTrigger(uint16_t t) { if (t < 20000) H_TRIGGERS[t] = 0; }
uint8_t readPStat(uint8_t i) { return H_PSTATS[i]; }
void writePStat(uint8_t i, uint8_t v) { H_PSTATS[i] = v; }
int32_t isDigimonRecruited(int32_t type)
{
	if ((uint32_t)type < 0x70) return isTriggerSet((uint16_t)(200 + type)) != 0;
	if ((uint32_t)type >= NUM_DIGIMON) return 0;
	return H_SPECIES_RECRUITED[type];
}
uint8_t *getScriptSection(uint8_t *script, uint16_t section)
{
	(void)script;
	return section == CITY_SECTION ? H_CITY_SECTION : 0;
}
void resetSpeciesFlags(void) {}
#define SHOP_REL 1
#define DGET_REL 2
void loadDynamicLibrary(int lib, uint8_t *a, int b, int c, int d) { (void)a; (void)b; (void)c; (void)d; H_LIB = lib; }

#include "equiv_gen.h" /* the extracted functions: o_recalc, t_recalc, o_topmap, ..., and the stub savegame */

/* ---- helpers */
static uint32_t rng_state = 12345;
static uint32_t rnd(void) { rng_state = rng_state * 1664525u + 1013904223u; return rng_state >> 8; }

typedef struct { uint8_t trig[2048]; uint8_t ps[256]; uint8_t rec[NUM_DIGIMON]; DigimonPara para[NUM_DIGIMON]; } Snap;
static void save(Snap *s) { memcpy(s->trig, H_TRIGGERS, sizeof(s->trig)); memcpy(s->ps, H_PSTATS, 256); memcpy(s->rec, H_SPECIES_RECRUITED, NUM_DIGIMON); memcpy(s->para, H_PARA, sizeof(H_PARA)); }
static void load(const Snap *s) { memcpy(H_TRIGGERS, s->trig, sizeof(s->trig)); memcpy(H_PSTATS, s->ps, 256); memcpy(H_SPECIES_RECRUITED, s->rec, NUM_DIGIMON); memcpy(H_PARA, s->para, sizeof(H_PARA)); }
static void clear(void) { memset(H_TRIGGERS, 0, 2048); memset(H_PSTATS, 0, 256); memset(H_SPECIES_RECRUITED, 0, NUM_DIGIMON); memset(H_PARA, 0, sizeof H_PARA); }
static void recruit(int s, int on) { if (s < 0x70) H_TRIGGERS[200 + s] = on; else H_SPECIES_RECRUITED[s] = on; }

static long cases, bad;
static void report(const char *name)
{
	printf("%-34s %9ld cases, %ld mismatches\n", name, cases, bad);
	if (bad) exit(1);
	cases = bad = 0;
}

/* ---- 1. prosperity (and the tournament clean-up that follows it in the same function) */
static void prosperity_case(void)
{
	static Snap in, a, b;
	save(&in);
	o_recalc(); save(&a); load(&in);
	t_recalc(); save(&b);
	cases++;
	if (memcmp(a.trig, b.trig, sizeof a.trig) || memcmp(a.ps, b.ps, sizeof a.ps)) {
		bad++;
		if (bad < 5) printf("MISMATCH prosperity: original p1=%d p3=%d, table p1=%d\n", a.ps[1], in.ps[3], b.ps[1]);
	}
	load(&in);
}

static void test_prosperity(void)
{
	int s, lv, i, k;
	/* every species alone, every level, recruited or not */
	for (s = 0; s < NUM_DIGIMON; s++)
		for (lv = 0; lv < 10; lv++) {
			clear(); H_PARA[s].level = lv; recruit(s, 1); prosperity_case();
			clear(); H_PARA[s].level = lv; prosperity_case();
		}
	report("prosperity: one species alone");
	/* everyone recruited at the same level */
	for (lv = 0; lv < 256; lv++) {
		clear();
		for (s = 0; s < NUM_DIGIMON; s++) { H_PARA[s].level = lv; recruit(s, 1); }
		prosperity_case();
	}
	report("prosperity: everyone, one level");
	/* random states: recruited bits, levels 0..9, p3 and the arena triggers, noise */
	for (i = 0; i < 300000; i++) {
		int p = rnd() % 101;
		clear();
		for (s = 0; s < NUM_DIGIMON; s++) {
			H_PARA[s].level = rnd() % 10;
			if ((int)(rnd() % 100) < p) recruit(s, 1);
		}
		H_PSTATS[3] = (i % 3 == 0) ? 0x16 + (rnd() % 3) : rnd();
		for (k = 0x25; k <= 0x27; k++) H_TRIGGERS[k] = rnd() & 1;
		for (k = 0; k < 10; k++) H_TRIGGERS[rnd() % 2048] = 1;
		prosperity_case();
	}
	report("prosperity: random states");
	/* the maximum: all of 3..58 recruited at their real levels is covered by tools/dws/testing/city_equivalence.py (content/species levels) */
}

/* ---- 2. the File City top map */
static void test_topmap(void)
{
	static const int T[5] = { 0xdc, 0xd6, 0xdd, 0xe1, 0xf6 };
	int m, n, k;
	for (m = 0; m < 32; m++)
		for (n = 0; n < 200; n++) {
			clear();
			for (k = 0; k < 40; k++) H_TRIGGERS[n ? rnd() % 2048 : 0] = 1;   /* noise: any trigger */
			for (k = 0; k < 5; k++) H_TRIGGERS[T[k]] = (m >> k) & 1;
			cases++;
			if (o_topmap() != t_topmap()) bad++;
		}
	report("top map: 32 states x 200 noises");
}

/* ---- 3. the revival screen (murd.c and dooa.c repeat the rule) */
static void test_revival(void)
{
	int a, b, p;
	for (a = 0; a < 2; a++)
		for (b = 0; b < 2; b++)
			for (p = 0; p < 256; p++) {
				clear(); H_TRIGGERS[0xdc] = a; H_TRIGGERS[0xd6] = b; H_PSTATS[1] = p;
				cases += 2;
				if (o_revival_murd() != t_revival_murd()) bad++;
				if (o_revival_dooa() != t_revival_dooa()) bad++;
			}
	report("revival: 2 x 2 x p1 0..255");
}

/* ---- 4. the maps that load the shop and arena overlays */
static void test_maps(void)
{
	int m, t, la, lb;
	for (t = 0; t < 2; t++)
		for (m = 0; m < NUM_DIGIMON; m++) {
			clear(); H_TRIGGERS[0x29] = t; H_LIB = 0; o_checkShopMap(m); la = H_LIB * 4 + H_TRIGGERS[0x29];
			clear(); H_TRIGGERS[0x29] = t; H_LIB = 0; t_checkShopMap(m); lb = H_LIB * 4 + H_TRIGGERS[0x29];
			cases++; if (la != lb) bad++;
			clear(); H_LIB = 0; o_checkArenaMap(m); la = H_LIB;
			clear(); H_LIB = 0; t_checkArenaMap(m); lb = H_LIB;
			cases++; if (la != lb) bad++;
		}
	report("maps: shop and arena, 0..1023");
}

/* ---- 5. the new game's start state */
static void test_start(void)
{
	static SavegameStubFile fa, fb;
	memset(&fa, 0xA5, sizeof fa); memset(&fb, 0xA5, sizeof fb);
	SAVE_FILE_STUB = &fa; o_init();
	SAVE_FILE_STUB = &fb; t_init();
	cases++;
	if (memcmp(&fa, &fb, sizeof fa)) {
		bad++;
		printf("MISMATCH start state: %d bytes differ\n", (int)sizeof fa);
	}
	report("start state: the whole save slot");
}

/* ---- the reader on any table: python (tools/dws/city.py) gives the table and the expected answers */
static int run_table(const char *path)
{
	static uint8_t buf[8192];
	static uint8_t sec[8192];
	FILE *f = fopen(path, "rb");
	size_t n;
	char line[16384];
	if (!f) return 2;
	n = fread(buf, 1, sizeof buf, f); fclose(f);
	memcpy(sec, buf, n); H_CITY_SECTION = sec;
	/* case: "T t1 t2 ... ; P p1 ; R sp1 sp2 ... ; L lv0 lv1 ..." (levels of species 0..) */
	while (fgets(line, sizeof line, stdin)) {
		char *p = line; int v, w; int mode = 0;
		clear(); memset(H_TRIGGERS, 0, sizeof H_TRIGGERS);
		for (v = 0; v < NUM_DIGIMON; v++) H_PARA[v].level = 0;
		while (*p) {
			if (*p == 'T' || *p == 'P' || *p == 'R' || *p == 'L') { mode = *p; p++; w = 0; continue; }
			if (*p >= '0' && *p <= '9') {
				v = strtol(p, &p, 10);
				if (mode == 'T' && v < 20000) H_TRIGGERS[v] = 1;
				else if (mode == 'P') H_PSTATS[1] = v;
				else if (mode == 'R') recruit(v, 1);
				else if (mode == 'L') { if (w < NUM_DIGIMON) H_PARA[w++].level = v; }
				continue;
			}
			p++;
		}
		{
			const uint16_t *st = cityStart();
			int top = cityTopMap(), rev = cityRevivalScreen();   /* before the recalculation: it overwrites pstat 1 */
			cityRecalcProsperity();
			printf("%d %d %d %d\n", top, rev, H_PSTATS[1], st[0]);
		}
	}
	return 0;
}

int main(int argc, char **argv)
{
	if (argc >= 3 && !strcmp(argv[1], "table")) return run_table(argv[2]);
	H_CITY_SECTION = 0;                 /* the original disc: no section, the built-in table */
	test_prosperity(); test_topmap(); test_revival(); test_maps(); test_start();
	printf("equivalent: the table readers give the original results on every case above\n");
	return 0;
}
