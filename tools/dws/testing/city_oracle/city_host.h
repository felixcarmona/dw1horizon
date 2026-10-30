/* Host stand-ins for the game's functions, so that build/decomp-story-state/src/main/city_rules.c and the
 * original C functions of decomp/src (extracted verbatim by tools/dws/testing/city_equivalence.py) can be run side by side with gcc.
 * docs/mods/city-rules.md, "Equivalence". */
#ifndef CITY_HOST_H
#define CITY_HOST_H

#include <stdint.h>
#include <string.h>

#ifndef ENGINE_TIER
#define ENGINE_TIER 2
#endif
#define NUM_DIGIMON 1024
#define SPECIES_FLAG_NONE 0

typedef struct { uint8_t level; } DigimonPara;

/* the state of the game that the rules look at */
extern uint8_t H_TRIGGERS[20000];		/* 1 byte per trigger (the tests of the story-state engine reach 17 183) */
extern uint8_t H_PSTATS[256];
extern uint8_t H_SPECIES_RECRUITED[NUM_DIGIMON];	/* species >= 0x70: the species bitset of the story-state engine */
extern DigimonPara H_PARA[NUM_DIGIMON];
extern uint8_t *H_CITY_SECTION;			/* the table in "MAPHEAD" (NULL: the original disc has none) */
extern uint8_t *MAPHEAD_SCRIPT_PTR;

int32_t isTriggerSet(uint16_t trigger);
void setTrigger(uint16_t trigger);
void unsetTrigger(uint16_t trigger);
uint8_t readPStat(uint8_t index);
void writePStat(uint8_t index, uint8_t value);
int32_t isDigimonRecruited(int32_t type);
uint8_t *getScriptSection(uint8_t *script, uint16_t section);
#define DIGI_PARA(type) (H_PARA[(type)])
#define DIGIMON_DATA H_PARA	/* the original reads DIGIMON_DATA[i].level */

#define CITY_SECTION 1260
#define CITY_MAGIC 0x5943
#define CITY_VERSION 1
#define CITY_START_STACKS 30
enum { CITY_BLOCK_PROSPERITY, CITY_BLOCK_TOP_MAP, CITY_BLOCK_REVIVAL, CITY_BLOCK_START, CITY_BLOCK_SHOP_MAPS, CITY_BLOCK_ARENA_MAPS, CITY_BLOCKS };

int32_t cityTopMap(void);
void cityRecalcProsperity(void);
int32_t cityRevivalScreen(void);
int32_t cityIsShopMap(int32_t mapId);
int32_t cityIsArenaMap(int32_t mapId);
const uint16_t *cityStart(void);

#endif
