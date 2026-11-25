# Signature effects

A species can play an effect of its own for one of its techniques, while every other Digimon that knows the
technique keeps the shared effect. Every imported species plays one for its finisher (179 of them), written for
this game: they are listed in [authored finishers](#authored-finishers) below. Their names and designs come from
the signature attacks of the games the species come from, listed in
[the signature attacks](../reference/signature-attacks.md).

## How a species gets one

- Its species JSON names the technique and the effect chunk:
  `"own_effect": {"technique": "Mega Flame", "chunk": 122}`. The technique must be one of its own techniques.
  `tools/species.py` writes them to the species record (`ownEffectTech` at 0x1CF, `ownEffectChunk` at 0x1D0).
- `getSpeciesTechEffect` (src/main/mod_species.c) is where the battle, the arena and the versus mode pick a
  technique's effect id, from the species and a move byte of its stats (it does the `DIGI_PARA` lookup the call
  sites did). It returns `0x100 + chunk` for that species and technique, and `0x100 + technique` for
  everything else. The technique keeps its number, power, range, cost and name. Only the picture and the hit
  test change.
- Chunks 122 and up are appended to `ETCHI/EFEDAT.EFE` after the disc's 122 by the derive step `effects`. The
  loader takes chunk ids up to 0x179 (index 377).
- `content/battle/own-effects.json` lists the chunks. Every entry is
  `{"name": ..., "technique": <species id>, "authored": <module>}`: the module is the file of
  `tools/technique_effects` that holds the effect (`finishers` or `finishers_<kind>`), and `technique` picks its
  function. The 40 effects of the technique rows (Darkness, Light, Water, Weapon, Earth) are entries of the same
  kind ([the technique rows](technique-rows.md)).
- Every effect is written here with the kit in `tools/technique_effects`: its pictures are painted by the code and
  its script, its flight and its hit are its own. No effect is converted from another game's disc and none is
  composed from the disc's own chunks. The build reads no effect file of another game: the converters that once
  made these chunks from Digimon World 2, Digimon World 2003 and Digital Card Battle are gone, and the patcher no
  longer checks or extracts those games' effect files (their format notes stay in
  [DW2](../reference/dw2-effects.md), [DW2003](../reference/dw3-effects.md) and
  [Card Battle](../reference/dcb-effects.md)).

## Authored finishers

All 179 imported species play a finisher effect written here from nothing: its pictures are painted by the code,
and its script, its flight and its hit are its own, so the finisher behaves as its design says (a shot that can be
dodged, a rain on a spot, a blast that reaches every enemy). They are written with the same kit as the new
technique rows ([the technique rows](technique-rows.md)), in `tools/technique_effects/finishers.py` (ten
species) and the nine `finishers_<kind>.py` files next to it (`shot_a`, `shot_b`, `dash_a`, `dash_b`, `beam_a`,
`beam_b`, `area`, `thrown`, `rain`, `close`), one function per species. An entry of
`content/battle/own-effects.json` names it: `{"name": ..., "technique": <species>, "authored": "<module>"}`, and
the species points at the chunk with `own_effect`. The design of each (what it shows, its kind, target and hits)
is in `content/finishers/imports.json` ([the finisher designs](unique-finishers.md)); every entry there has
`effect.status` `authored`.

What the engine allows: a finisher deals one damage event per target per cast, so the extra hits of a design are
visual. 34 of the finishers fly to the place where the target stood and can be dodged by a target that walks
away (the list is `FINISHERS_DODGED` in `tools/test_technique_effects.py`); the others hit as they land.
`tools/test_technique_effects.py` builds each one, plays it in the simulator to its end and checks that it hits what
its design says, and that the 34 that fly miss a target that walks away.

The table is made from the two data files, sorted by species id. "What plays" is `behavior.look`.

| Chunk | Finisher | Species | Module | What plays | Hits |
|---|---|---|---|---|---|
| 251 | Wolf Claw | 62 WereGarurumon | `finishers_dash_a` | Cold glints run to the paws, a blue streak leaps at the target and two rakes of three claws tear across it one after the other. | one enemy |
| 124 | Darkness Gear | 122 Hagurumon | `finishers_thrown` | A black cog winds up before Hagurumon in a dark haze, rolls into the target and grinds on it in a shower of sparks before flying apart. | one enemy |
| 376 | Recovery Power | 123 Tinmon | `finishers_beam_a` | Snowflakes gather into a lamp on the chest, a thin cold beam with frost hoops running down it opens a great snowflake on the target. | one enemy |
| 252 | Brachio Bubble | 126 Brachiomon | `finishers_shot_a` | A bubble swells at the mouth to the size of a Digimon, wobbles after the target with small bubbles in its wake and bursts on it in a ring of spray. | one enemy |
| 253 | Vee Head Butt | 180 Veemon | `finishers_dash_a` | A blue light swells on the brow and shoots head first at the target as a blunt comet, and a great white V flashes up where it butts. | one enemy |
| 254 | Puppet Pummel | 181 Puppetmon | `finishers_dash_a` | Three wooden mallets drop on strings onto the target, left, right and middle, each knocking a jagged star and splinters out of it. | one enemy |
| 125 | Poison Wing | 182 Kimeramon | `finishers_shot_a` | Both wings glow and each throws a front of sickly green heat; the two close on the target and it goes up in green and orange flame. | one enemy |
| 255 | Sticky Net | 183 Wormmon | `finishers_shot_a` | A spat ball of silk opens in the air into a turning net that falls over the target and draws tight round it. | one enemy |
| 256 | Hawk Beam | 184 Hawkmon | `finishers_beam_a` | A glint on the brow feather fires a hair-thin red beam that stings the target with a star and leaves red feathers tumbling. | one enemy |
| 257 | Diamond Shell | 185 Armadillomon | `finishers_dash_a` | A curled, plated ball rolls along the ground at the target kicking up dust and bounces off it in a burst of grit. | where the target stood: can be dodged |
| 258 | Spiking Strike | 187 Stingmon | `finishers_dash_a` | A pink point lights on the wrist, two feints flick out, then a long green spike runs the target through and sparks fly out of its far side. | one enemy |
| 259 | Mach Impulse | 188 Aquilamon | `finishers_dash_a` | A light climbs into the air and dives on the target as a white dart, leaving shock rings in the sky and three booming rings where it lands. | one enemy |
| 260 | Tail Hammer | 189 Ankylomon | `finishers_close` | A spiked ball of stone swings over in a high arc and slams down on the target; rocks fly, dust rolls out in a ring and the ground jumps a second time. | one enemy |
| 261 | Celestial Arrow | 190 Angewomon | `finishers_shot_a` | A golden bow forms as light gathers on it and looses one arrow of rose light that breaks in a cross of light and falling feathers; it can be dodged. | where the target stood: can be dodged |
| 262 | Metal Wolf Claw | 191 MetalGarurumon | `finishers_beam_a` | A broad freezing beam from the jaws sheds rime and raises spikes of ice round the target that shatter. | one enemy |
| 263 | Positron Laser | 192 Imperialdramon | `finishers_beam_a` | Hoops close on the arm cannon, then a huge orange beam with hoops racing down it whitens the screen and bursts on the target. | one enemy |
| 264 | Gold Rush | 193 Digmon | `finishers_rain` | Five spinning golden drills fly out one after another on bright wakes and bore into the target in bursts of gold chips. | one enemy |
| 265 | Ex-Laser | 194 ExVeemon | `finishers_beam_a` | The X on the chest swells, tears loose and flies at the target as a growing burning X that stamps it with a blaze. | one enemy |
| 266 | Fire Rocket | 195 Flamedramon | `finishers_dash_a` | Flames wreathe the caster and leave it as a lance of fire with two flames corkscrewing round it, which blows a cone of fire out of the target. | where the target stood: can be dodged |
| 267 | Tempest Wing | 196 Halsemon | `finishers_beam_a` | Wind whips round the caster and drills to the target as a sideways whirlwind of hoops and coiling streaks that blows apart on it. | one enemy |
| 268 | Plasma Shot | 197 Magnamon | `finishers_rain` | Four crackling plasma orbs charge above the caster, then dive one by one and burst on the target in white-gold flares. | one enemy |
| 269 | Rocking Stone | 198 Nefertimon | `finishers_thrown` | Two carved stone tablets form in shafts of sunlight over the target and drop one after the other in dust and chips of stone. | one enemy |
| 167 | Desperado Blaster | 199 Paildramon | `finishers_rain` | Two hip guns fire in turn a row of blue tracers with muzzle flashes and flung cases, each flaring and sparking on the target before a last star burst. | one enemy |
| 271 | Star Shower | 200 Pegasusmon | `finishers_rain` | A shower of five-pointed stars falls from the sky on glittering tails and bursts on the target one after another. | one enemy |
| 272 | Lightning Blast | 201 Lighdramon | `finishers_beam_a` | A jagged bolt that changes shape every instant stands between the jaws and the target while arcs crawl over it. | one enemy |
| 273 | Submarine Attack | 202 Submarimon | `finishers_dash_a` | Bubbles rise and a sonar ring pings out, then a steel torpedo runs at the target in a wake of foam and throws up a column of spray. | where the target stood: can be dodged |
| 274 | V-Nova Blast | 203 Veedramon | `finishers_beam_a` | It throws its head back and an arrowhead of white-blue light swells in its open jaws, already lying along the line of the shot; when the head comes down that same arrowhead is breathed out, fast at first and growing all the way to the target on the point of a ray that widens behind it; there it opens out and melts into the burst as the ray dims away. | one enemy |
| 275 | Horn Buster | 205 MegaKabuterimon | `finishers_beam_a` | Arcs feed a ball of lightning swelling on the horn; it is flung in a straight line and bursts in a ringed shock, leaving current on the target. | where the target stood: can be dodged |
| 276 | Gate of Destiny | 206 MagnaAngemon | `finishers_beam_a` | A spark draws a golden round gate behind the target; it opens on white light, pulls lights out of the target and flares. | one enemy |
| 277 | Seventh Heaven | 207 Seraphimon | `finishers_rain` | Seven holy orbs turn as a wheel around the caster, then strike the target in turn under a pillar of light and drifting feathers. | one enemy |
| 278 | Needle Spray | 208 Togemon | `finishers_rain` | A green whirl spins at the caster and sprays volleys of white needles that prick the target in green bursts. | one enemy |
| 279 | Flower Cannon | 209 Lillymon | `finishers_beam_a` | A pink flower opens and turns between the hands and fires a green beam that bursts on the target in a cloud of petals. | one enemy |
| 280 | X-Scissor Claw | 210 GranKuwagamon | `finishers_dash_a` | Two violet mandibles close on the target from either side in two crossing cuts, and the black X they leave bursts. | one enemy |
| 281 | River of Power | 211 MetalSeadramon | `finishers_beam_a` | Hoops close on the nose cannon and a thick river of blue power sprays drops and raises a column of water on the target. | one enemy |
| 282 | Venom Infusion | 212 VenomMyotismon | `finishers_beam_a` | A toothed maw opens on the chest and pours a crimson blast with a black heart that leaves a dark blot and rising red bubbles. | one enemy |
| 283 | V Wing Blade | 213 AeroVeedramon | `finishers_beam_a` | Lights from the two wingtips meet at the chest and a V-shaped blade of light is flung straight ahead, growing, with echoes behind it. | where the target stood: can be dodged |
| 162 | Clay Bomb | 214 Shakkoumon | `finishers_thrown` | Three clay figures tumble in high arcs onto the target's spot and burst into potsherds and red dust. | where the target stood: can be dodged |
| 285 | Fire Tornado | 215 Magnadramon | `finishers_beam_a` | Two ropes of rose flame coil round each other to the target and wind up into a spinning funnel of fire. | one enemy |
| 374 | Crimson Claw | 216 Devidramon | `finishers_dash_a` | Four red eyes open, a red streak lunges at the target and three talons rake down through it side by side, dragging trails of red. | one enemy |
| 287 | Marching Fishes | 217 Gomamon | `finishers_rain` | A file of blue and striped orange fish leaps out in arcs and slaps into the target with splashing crowns of water. | one enemy |
| 288 | Harpoon Torpedo | 218 Ikkakumon | `finishers_shot_a` | The horn leaves the head on a jet of flame trailing smoke and bursts into frost and splinters of ice; it can be dodged. | where the target stood: can be dodged |
| 289 | Vulcan's Hammer | 219 Zudomon | `finishers_close` | Sparks run up into a hammer hanging over the target; it drops, and rings of energy burst out twice with bolts dancing over the spot. | one enemy |
| 290 | Arctic Blizzard | 220 Vikemon | `finishers_close` | Two spiked balls of ice whirl round Vikemon, then a gale of snow and flakes blows over the target and spikes of ice grow from the ground under it and break. | one enemy |
| 291 | Puppy Howling | 221 Salamon | `finishers_beam_a` | Four howls leave the mouth as widening sound rings with tumbling notes and keep ringing over the target. | one enemy |
| 292 | Cat's Eyes | 222 BlackGatomon | `finishers_beam_a` | The light dims, two yellow cat's eyes open and flash, violet ripples cross to the target and huge eyes open over it in a violet haze. | one enemy |
| 293 | Darkness Wave | 223 LadyDevimon | `finishers_rain` | A swarm of bats pours out of a cloud of gloom and tears across the target in violet slashes before scattering. | one enemy |
| 164 | Trident Arm | 224 MetalGreymonVaccine | `finishers_thrown` | The metal claw shoots out on a chain, clamps the target in a burst of sparks, wrenches it and reels back. | one enemy |
| 294 | Double Stars | 225 Shurimon | `finishers_thrown` | Two great shuriken spin up at Shurimon's sides in a swirl of leaves and are flung straight at the target one after the other. | where the target stood: can be dodged |
| 295 | Top Gun | 226 Silphymon | `finishers_shot_a` | A light from each hand joins into a red and white sphere with wind wound round it; thrown, it breaks on the target in a whirl of gusts. | one enemy |
| 296 | Angry Spike | 227 Apemon | `finishers_thrown` | The bone club is hurled end over end in a high arc, lands with a crack, splinters and dust, and bounces away. | where the target stood: can be dodged |
| 297 | Dancing Meteor | 228 Baronmon | `finishers_rain` | Burning rocks spiral down in a dance and crash on the spot where the target stood in bursts of fire. | where the target stood: can be dodged |
| 298 | Shadow Scythe | 229 Phantomon | `finishers_dash_a` | Wisps of shadow gather, a dark spinning crescent flies to the target and reaps through it in one wide pale sweep. | one enemy |
| 299 | Thorny Whipping | 230 Rosemon | `finishers_close` | A thorned vine lashes the target three times, high, low and over the top, each crack throwing rose petals and leaves. | one enemy |
| 300 | Shell Attack | 231 ShellNumemon | `finishers_dash_a` | Slime bubbles up and a pink spiral shell is lobbed high, spinning and dripping, lands on the target's head and bounces off in a green splash. | one enemy |
| 301 | Free Throw Bomb | 232 BomberNanimon | `finishers_thrown` | A big round bomb with a spitting fuse is lobbed high and goes up in a fireball, a blast ring and rolling black smoke. | where the target stood: can be dodged |
| 302 | Boiling Bubble | 233 RedOtamamon | `finishers_shot_a` | Three scalding bubbles blown one after another hop through the air steaming and burst on the target in boiling water. | one enemy |
| 375 | Lightning Paw | 234 Gatomon | `finishers_dash_a` | Gold sparks crackle on the paw, a bolt jumps to the target and a great glowing paw print stamps on it in a shower of stars. | one enemy |
| 304 | Flame Bomber | 235 Candlemon | `finishers_shot_a` | The head flame swells, tears free and is flung in a high arc dripping wax; a ring of small flames stands up where it lands; it can be dodged. | where the target stood: can be dodged |
| 163 | Demi Dart | 236 DemiDevimon | `finishers_thrown` | A syringe loaded with violet serum is thrown like a dart, dripping as it flies, and bursts in a violet spray. | where the target stood: can be dodged |
| 306 | Inferno Missile | 237 Diaboromon | `finishers_beam_b` | A hollow red ball with a black heart swells on the chest and tears open into a ragged red torrent with a black core that bursts on the target and leaves soot. | one enemy |
| 307 | Pulse Blast | 238 Dolphmon | `finishers_beam_b` | Six rings of sound leave the head one after another, swelling as they swim to the target and breaking on it in ripples. | one enemy |
| 308 | Spiral Saw | 239 Gizamon | `finishers_dash_a` | A toothed teal blade spins up, runs at the target throwing sparks, bites in and grinds there before the cut goes through. | one enemy |
| 309 | Coral Crusher | 240 Gesomon | `finishers_shot_a` | Three jagged lumps of coral hurled one after another, each spinning in a sheath of sea water and breaking where it lands; they can be dodged. | where the target stood: can be dodged |
| 310 | Thunder Ball | 241 Wizardmon | `finishers_shot_a` | Sparks at the tip of the staff knot into a ball of lightning that rolls after the target and forks out all round it. | one enemy |
| 168 | Crystal Cloud | 242 Sorcermon | `finishers_close` | A sparkling fog rolls from the staff to the target and closes round it; six ice crystals circle in the fog, draw in and shatter together. | one enemy |
| 312 | Meteor Stream | 243 Starmon | `finishers_rain` | A burning gate opens high above the caster and a stream of bright stars pours down from it on fiery tails into the target. | one enemy |
| 313 | Comet Cluster | 244 SuperStarmon | `finishers_rain` | A cluster of cold blue comets plunges from the sky on tall wakes onto the spot where the target stood and ends in a white nova. | where the target stood: can be dodged |
| 314 | Trump Sword | 245 Piedmon | `finishers_thrown` | Four swords appear in a fan over Piedmon with a wink of magic, then fly at the target one after another on pink trails. | one enemy |
| 371 | Hades' Grenade | 246 Infermon | `finishers_shot_a` | Darkness gathers in the mouth into a black ball veined with fire, shot straight and smoking; it bursts into a pillar of hellfire; it can be dodged. | where the target stood: can be dodged |
| 316 | Mini Scissor Claws | 247 Kokuwamon | `finishers_close` | Current hums on Kokuwamon; two toothed steel blades snap shut on the target from the sides, then two more from above and below, and the current jumps over it. | one enemy |
| 372 | Ocean Love | 248 MarineAngemon | `finishers_shot_a` | Three bubbles with a pink heart in each float swaying into the target and burst into small hearts; a great heart opens over it at the end. | one enemy |
| 318 | Freezing Wave | 249 Quetzalmon | `finishers_close` | Five growing fronts of freezing wind cross to the target one after another; the first freezes it in a star of frost and icy feathers fly from each that follows. | one enemy |
| 319 | Flare Buster | 250 Shadramon | `finishers_beam_b` | A ball of fire on the horn stretches into a spear of flame that runs through the target and leaves flames standing along its path. | one enemy |
| 320 | Solar Flare | 251 Solarmon | `finishers_beam_b` | The face becomes a small sun with a flickering corona, the field whites out and a fan of rays leaves it, the middle one burning the target. | one enemy |
| 321 | Thunder Volt | 252 Thundermon | `finishers_shot_a` | Current crackles on both maces and two crooked strokes of lightning meet on the target, holding it in a cage of sparks. | one enemy |
| 322 | Slamming Tusk | 253 Tuskmon | `finishers_dash_a` | Dust is pawed up and two great ivory tusks plough across the ground, gore the target and toss upward, throwing stones and dust. | one enemy |
| 373 | Torpedo Attack | 254 Tylomon | `finishers_shot_a` | Two torpedoes leap from the back, arc over and dive at the spot where the target stands, each throwing up a column of water; they can be dodged. | where the target stood: can be dodged |
| 324 | Feral Sword | 255 Valkyrimon | `finishers_dash_a` | A sword of light forms overhead and falls into one widening cut that passes through the target as a bright line, with white feathers after it. | one enemy |
| 377 | Jamming Thunder | 256 VioletElecmon | `finishers_beam_b` | A crooked violet bolt in three restless legs jumps to the target and leaves the air around it broken into blocks of static. | one enemy |
| 126 | Tri-Horn Attack | 257 Triceramon | `finishers_dash_a` | Three lights and a triangle kindle at the horns, three blue horns fly and meet on the target, and a three-pointed gold star breaks out. | one enemy |
| 127 | Howling Crusher | 258 SaberLeomon | `finishers_dash_b` | SaberLeomon roars, and the roar leaves it as a lion's head of amber light that bounds across the ground in one leap, fangs first; | one enemy |
| 128 | Duo Scissor Claw | 259 Okuwamon | `finishers_area` | Two great stag pincers open wide at the caster's sides and snap shut twice across the whole enemy line, each bite leaving crossed cuts on everyone. | every enemy |
| 129 | Nuclear Laser | 260 MetalTyrannomon | `finishers_shot_a` | A living missile leaves the arm on a thread of smoke and hunts the target down; the field flashes and a green fireball climbs while ash falls. | one enemy |
| 130 | Strong Carapace | 261 Tortomon | `finishers_area` | The spiked shell rises over the caster and fires three volleys of horn spikes that arc up and stab down on every enemy. | every enemy |
| 131 | Brown Stinger | 262 Flymon | `finishers_shot_a` | The tail spits three long stingers in a burst; they drive into the target and violet venom spatters and bubbles up. | one enemy |
| 165 | Fungus Cruncher | 263 Mushroomon | `finishers_shot_a` | A small toadstool lobbed tumbling at the target bursts over it in a violet cloud that hangs there shedding spores. | one enemy |
| 123 | Buffalo Breath | 264 Raremon | `finishers_close` | A rolling green-brown gas swells as it crosses to the target and hangs on it, bubbling, dripping and reeking. | one enemy |
| 132 | Fire Blast | 265 DarkTyrannomon | `finishers_area` | A long breath of red fire gouts from the caster's jaws and sweeps over the field, leaving every enemy licked by flames. | every enemy |
| 133 | Pretty Attack | 266 ExTyrannomon | `finishers_shot_a` | A kiss pops on the lips and turns into a big beating heart that drifts into the target; hearts and stars circle its head. | one enemy |
| 134 | Tusk Crusher | 267 Mammothmon | `finishers_dash_b` | Mammothmon stamps twice, raising dust, and a pair of great ivory tusks ploughs along the ground to the target in a cloud; they gore upwards through it and stones fly. | one enemy |
| 135 | S-Bone Crusher | 268 SkullMammothmon | `finishers_area` | A giant bone spins out in a wide boomerang curve through the enemy line, cracking each enemy as it passes, and shatters into splinters. | every enemy |
| 136 | Junk Chunker | 269 Garbagemon | `finishers_thrown` | A tin, a fish bone and an old boot are slung out of the can and land in splats of green stench and flies. | where the target stood: can be dodged |
| 137 | Smiley Warhead | 270 PrinceMamemon | `finishers_shot_b` | A grinning bomb is lobbed in a high arc with a sputtering fuse, laughs as it lands and goes up in fire, smoke and stars. | one enemy |
| 138 | Sad Water Blast | 271 Plesiomon | `finishers_area` | A mournful cry gathers falling tears over the caster's head, then a tall wall of water rolls out and breaks over every enemy. | every enemy |
| 139 | Twig Tap | 272 Woodmon | `finishers_close` | A forked branch swings down on the target from above, then back up from below, each tap with a smack and a burst of leaves and splinters. | one enemy |
| 140 | Rain of Pollen | 273 Floramon | `finishers_shot_b` | A slow yellow cloud glittering with pollen rolls from the flower hands to where the target stood and settles there. | where the target stood: can be dodged |
| 141 | Ninja Flower | 274 Blossomon | `finishers_area` | Four volleys of spinning flower shuriken fly out trailing leaves and petals and burst on every enemy. | every enemy |
| 142 | Tail Blade | 275 Scorpiomon | `finishers_dash_b` | Scorpiomon's tail uncoils over its head segment by segment, the blade at its end held high above the target; | one enemy |
| 166 | Kongou | 276 Baihumon | `finishers_dash_b` | Six plates of adamant close round Baihumon into a shell that rings as it hardens; | one enemy |
| 122 | Metal Fireball | 277 SkullMeramon | `finishers_area` | A ball of molten metal wrapped in blue flame is forged, lobbed high and bursts on the enemies, raining burning slag on each of them. | every enemy |
| 143 | Spurting Ink | 278 Octomon | `finishers_shot_b` | Three gouts of black ink are spat one after another trailing drops; the one that lands blots the target and splashes all around. | where the target stood: can be dodged |
| 144 | Evil Wind | 279 MarineDevimon | `finishers_area` | Dark ink gusts curl out from the caster in a spreading foul wind that wraps every enemy in black-violet swirls. | every enemy |
| 145 | Trick or Treat | 280 Pumpkinmon | `finishers_area` | A grinning pumpkin is conjured overhead, drops among the enemies and bursts, throwing rind and candy-coloured sparks over all of them. | every enemy |
| 146 | Hyper Heat | 281 Cyclonemon | `finishers_close` | Rings of heat draw in on Cyclonemon's arm and a white-hot jet runs to the target and holds on it, molten drops spraying from where it bites. | one enemy |
| 147 | Pummel Peck | 282 Kiwimon | `finishers_shot_b` | A little kiwi bird pelts along the ground at the target kicking up dust and bursts into feathers on whoever it runs into. | where the target stood: can be dodged |
| 148 | Pearl Shot | 283 Syakomon | `finishers_shot_b` | Light wells up in the open shell and a pearl flies out trailing bubbles, bursting on the target in a crown of water. | one enemy |
| 149 | Scissor Magic | 284 Crabmon | `finishers_close` | A great red claw opens beside the target and snaps shut on it, then a bigger one snaps again; each snap leaves a crossed glint and rising bubbles. | one enemy |
| 150 | E-Stun Blast | 285 Gazimon | `finishers_shot_b` | A crackling ball of current is spat from the jaws along a jagged path and bolts stab down where it lands, leaving it twitching. | where the target stood: can be dodged |
| 151 | Royal Smasher | 286 Deramon | `finishers_thrown` | An egg is fired like a shell with a bang and a smoke ring, and cracks open on the target in a burst of yolk and shell. | where the target stood: can be dodged |
| 152 | Waking Dream | 287 Tapirmon | `finishers_shot_b` | A winding trail of violet dream-smoke closes over the target, an eye opens in the coil, stares, and the nightmare bursts. | one enemy |
| 153 | Tomahawk Crunch | 288 Boltmon | `finishers_area` | The battle axe is hurled spinning through the enemy line and comes back for a second pass, sparking on every enemy both times. | every enemy |
| 154 | Chaos Cannon | 289 ChaosLord | `finishers_area` | A cannon charge of unstable energy swells at the muzzle and fires a wide shell that detonates in a ragged chaos burst over every enemy. | every enemy |
| 155 | Chrono Breaker | 290 Clockmon | `finishers_shot_b` | A clock face of light opens over the target with racing hands that snap to twelve; the field greys as time stops and the dial breaks in rings. | one enemy |
| 156 | Tentacle Claw | 291 Dragomon | `finishers_thrown` | The trident is thrown out of a swirl of dark water, trailing spray, and a spout of sea shoots up where it strikes. | where the target stood: can be dodged |
| 157 | Triple Forces | 292 Deltamon | `finishers_area` | Three heads fire a red, a blue and a yellow orb one after another; they land in turn and merge into a three-coloured blast on every enemy. | every enemy |
| 158 | Legendary Blade | 293 Gryphonmon | `finishers_area` | A beat of golden wings throws a broad crescent blade of light that sweeps across the field, cutting every enemy amid falling feathers. | every enemy |
| 159 | Digital Bomb | 294 Datamon | `finishers_area` | Four data bombs are lobbed in sequence, each locking on with target brackets and bursting into pixels and digits over the enemies. | every enemy |
| 196 | Nightmare Shock | 295 Vilemon | `finishers_beam_b` | The field darkens, a slit of light opens at the eye and a writhing rope of shadow reaches the target while rings of dusk close in on it. | one enemy |
| 223 | Maul Attack | 296 Grizzlymon | `finishers_dash_b` | A bear's paw of blue light as big as the target swings down on it from above and to one side, leaving four gashes; a second set crosses the first. | one enemy |
| 197 | Mugen Hadou | 297 Marsmon | `finishers_beam_b` | Flames climb round the caster and a burning fist flies out, growing as it goes, then a flurry of smaller fists hammers the same spot. | one enemy |
| 198 | Poison Cobweb | 298 Dokugumon | `finishers_shot_b` | A knot of silk unfolds into a wide web in flight and wraps the target while venom runs along the threads and boils off in green fumes. | one enemy |
| 199 | Captain Cannon | 299 Hookmon | `finishers_shot_b` | The ship cannon fires in a tongue of flame and a roll of smoke, and the iron ball flies low and breaks on whoever it meets in fire and splinters. | where the target stood: can be dodged |
| 200 | Golden Ripper | 300 SlashAngemon | `finishers_dash_b` | Feathers drift from SlashAngemon's wings; | one enemy |
| 201 | Atomic Ray | 302 HiAndromon | `finishers_beam_b` | An atom lights up on the chest, a hair-thin line finds the target and a hard green-white ray with six-sided collars follows it. | one enemy |
| 202 | Dark Spirits DX | 303 KingEtemon | `finishers_area` | A dark sphere with a sneering face swells over the caster and bursts into a concert of sound waves and musical notes that rolls over every enemy. | every enemy |
| 224 | Striking Fish | 304 Divermon | `finishers_shot_b` | A harpoon fish darts in a straight line in a sleeve of spray and bubbles and drives into whoever is in its way, throwing up a fan of water. | where the target stood: can be dodged |
| 225 | Pincer Crusher | 305 Ebidramon | `finishers_close` | Two toothed jaws of water close over and under the target, press with rings of pressure drawing in, then crush: ice and water burst out and a spout stands where it was. | one enemy |
| 226 | Cyclone Turbine | 306 GrapLeomon | `finishers_dash_b` | The wind gathers round GrapLeomon and leaves as a turbine of teal whirlwinds, one behind another, that bores across to the target and stands up there as a twister. | one enemy |
| 169 | Royal Muck | 307 BlackKingNumemon | `finishers_thrown` | A crowned lump of muck wobbles through a lazy arc and lands with a splat and a foul cloud; the crown pops off and tumbles down. | where the target stood: can be dodged |
| 228 | Lizard Dance | 308 Dinohyumon | `finishers_dash_b` | Four times a green blur darts through the target from a different side, kicking up dust where it sets off, and each time a burning cut is left across it; | one enemy |
| 170 | Bunny Blades | 309 Antylamon | `finishers_dash_b` | Antylamon's arms become axes: one great blade swings down across the target from the right, a second from the left, each leaving a heavy wake; | one enemy |
| 203 | Justice Strike | 310 Assaultmon | `finishers_rain` | Machine-gun tracers rake the target from a starred muzzle, then rockets arc over on smoke trails and blast it. | one enemy |
| 171 | Spirit Needle | 311 Arukenimon | `finishers_shot_b` | Threads of light draw into one long needle that crosses the field in a blink leaving a pink line in the air and a cross of light where it pierces. | where the target stood: can be dodged |
| 204 | Evil Inferno | 312 Creepymon | `finishers_area` | The ground glows and pillars of hellfire with screaming faces erupt under every enemy at once. | every enemy |
| 205 | Bulb Flash | 313 Bulbmon | `finishers_beam_b` | A glass bulb over the caster stutters on and off, then catches: the field goes white, spokes of glare shoot out and a broad shaft pins the target. | one enemy |
| 174 | Nail Bone | 314 SkullSatamon | `finishers_beam_b` | A stone above the caster fills with sick yellow light and throws a beam wrapped in black lightning; a pale skull rises out of the target. | one enemy |
| 232 | Talisman of Light | 315 Taomon | `finishers` | A paper charm thrown at the target that opens into a seal of light. | one enemy |
| 206 | Amethyst Mandala | 316 Sakuyamon | `finishers` | A violet wheel of petals opens from her and reaches every enemy. | every enemy |
| 207 | Divine Wind | 317 Fujinmon | `finishers_area` | A white whirlwind spins up around the caster and spreads outwards, carrying paper charms through every enemy. | every enemy |
| 208 | Final Purification | 318 Gallantmon | `finishers` | A ray of holy light from the shield. | one enemy |
| 176 | Pyramid Power | 319 Pharaohmon | `finishers_beam_b` | A line of gold goes up and draws a pyramid of light around the target edge by edge, then a shaft of gold pours down inside it and turquoise ankhs rise. | one enemy |
| 370 | Plasma Blade | 320 Growlmon | `finishers` | Two crossing cuts of the plasma blades, close up. | one enemy |
| 235 | Berserk Sword | 321 Knightmon | `finishers_dash_b` | Rage burns red round Knightmon while a sword of steel as tall as a house takes shape in the air over the target; | one enemy |
| 236 | Blade Twister | 322 Kyukimon | `finishers_dash_b` | The wind whirls up round Kyukimon and throws a wheel of three sickles that spins across the field; | where the target stood: can be dodged |
| 209 | Blazing Mane | 323 Lynxmon | `finishers_close` | Lynxmon's mane flares up in a crown of curling flames shedding sparks, then a widening cone of fire rolls to the target and leaves it burning. | one enemy |
| 237 | Mail Bomber | 324 Maildramon | `finishers_shot_b` | Three finned bombs climb from the back on smoke and whistle straight down on the target one after another, each bursting in fire and iron. | one enemy |
| 238 | Ura Sword | 325 Musyamon | `finishers_dash_b` | Ghost lights climb round Musyamon. | one enemy |
| 210 | Atomic Blaster | 326 WarGrowlmon | `finishers` | Twin red beams from the chest cannons. | one enemy |
| 181 | Gargoyle Rush | 327 Gargoylemon | `finishers_dash_b` | White streaks shoot up from Gargoylemon into the sky; | one enemy |
| 239 | Twin Sickles | 328 Snimon | `finishers_thrown` | Two green crescents peel from Snimon's scythes, sweep wide to either side and close on the target like shears in a white X. | one enemy |
| 212 | Necro Eye | 329 Ghoulmon | `finishers_beam_b` | A great red eye opens lid by lid and looses a needle of red light with motes winding round it; pale wisps drift up out of the target. | one enemy |
| 240 | Darkside Quake | 330 Minotarumon | `finishers_area` | The hammer arm slams the ground and a shockwave of flying rock spikes and rubble runs out from the caster under every enemy. | every enemy |
| 185 | Vemmon Crash | 331 Vemmon | `finishers_close` | Dashed rings close on Vemmon; | one enemy |
| 242 | Roach Rush | 332 Roachmon | `finishers_dash_b` | Ten cockroaches scuttle out from under Roachmon and race across the ground in zigzags, leaving a stink behind them; | one enemy |
| 213 | Raijin Thunder | 333 Raijinmon | `finishers_area` | A ring of thunder drums lights up above the caster beat by beat, then lightning bolts fall on every enemy at once. | every enemy |
| 214 | Necrophobia | 334 Mummymon | `finishers_shot_b` | A gunshot: a white muzzle flash and an instant streak, then a pale skull rises through the target with wisps of grave-mist. | one enemy |
| 215 | Giant Missile | 335 MegaGargomon | `finishers_shot_b` | Two great shoulder missiles ignite and fly on roaring flames trailing smoke, landing one after the other in two huge explosions. | one enemy |
| 189 | Raiden Strike | 336 Raidenmon | `finishers_beam_b` | A spark thrown into the sky piles storm cloud over the target, which lets go two forked bolts while the field flashes and current crawls on the ground. | one enemy |
| 244 | Hot Head | 351 Kotemon | `finishers_dash_b` | Flames climb Kotemon's bamboo sword; | one enemy |
| 216 | Swing Swing | 352 Monmon | `finishers_close` | A golden star swings in a spiral round the target and smacks into it, then a wider one swings the other way and smacks harder; | one enemy |
| 245 | Bear Fist | 353 Bearmon | `finishers_close` | Light gathers on Bearmon's paw; a great glowing fist drives straight into the target, growing as it comes, and three rings of the blow go on through it. | one enemy |
| 246 | Diamond Storm | 354 Renamon | `finishers` | Crystal shards form overhead and rain on the spot where the target stood. | one enemy |
| 326 | Terra Force | 373 WarGreymon | `finishers_shot_b` | Fire streams up from the ground into a small rayed sun overhead that is hurled down and raises a wall of flame and burning rock through the target. | one enemy |
| 327 | Darkness Zone | 400 Apocalymon | `finishers_shot_b` | Slivers of dark fall in on the target as the field dims, a black sphere with a torn violet rim and turning five-sided walls closes round it, then collapses and shatters. | one enemy |
| 160 | Needle Squall | 401 Pukumon | `finishers_area` | The body puffs up and bursts six waves of needles outwards in all directions, riddling every enemy. | every enemy |
| 161 | Blind Attack | 402 NeoCrimson | `finishers_dash_b` | Two red eyes open over NeoCrimson and the field goes dark. | one enemy RANDOM |
| 190 | Corona Blaster | 403 Beelzemon | `finishers` | Three shots from the arm cannon through a drawn seal. | where the target stood: can be dodged |
| 248 | Terra Destroyer | 404 BlackWarGreymon | `finishers` | A black sun gathered overhead and thrown down; its blast reaches every enemy. | every enemy |
| 217 | Dynamo Cannon | 405 Cannondramon | `finishers_beam_b` | Two dynamos spin up over the shoulders and fire six blue shells by turns, each bursting orange on the target. | one enemy |
| 218 | Melting Blood | 406 MaloMyotismon | `finishers_close` | Blood wells in MaloMyotismon's hand and runs out into a swaying whip that lashes the target and clings to it, dripping; | one enemy |
| 219 | Ultimate Flare | 407 Armageddemon | `finishers_beam_b` | Embers stream into the jaws and come back as a widening cone of crimson and gold fire with three blasts inside it and black smoke after. | one enemy |
| 220 | Water Spiral | 408 Suijinmon | `finishers_beam_b` | Two ropes of water corkscrew round one another to the target, where a spout bursts up and falls back as rain. | one enemy |
| 249 | Dragon Wheel | 409 Kyubimon | `finishers` | A wheel of blue fire that flies as a dragon; it can be dodged. | where the target stood: can be dodged |
| 221 | Zanba Blade | 430 Zanbamon | `finishers_dash_b` | Dust rises under Zanbamon's hooves as it lifts a sword longer than the gap between the fighters; | one enemy |
| 194 | Data Crusher | 431 Kurisarimon | `finishers_shot_b` | A block of raw data is compiled from streaming ones and zeroes, stutters across the field and breaks over the target in squares and scan lines. | one enemy |
| 195 | Cat Laser | 432 Bastemon | `finishers_beam_b` | Two green cat's eyes open over the caster and loose thin rose rays that sweep in to cross on the target in a star of light and a scatter of jewels. | one enemy |
| 222 | Pyrosphere | 433 Guilmon | `finishers` | A ball of fire grown in the mouth and spat at the target; it can be dodged. | where the target stood: can be dodged |
| 328 | Wing Blade | 460 Garudamon | `finishers_shot_b` | Flames knit into a great bird of fire overhead that dives in a straight line shedding burning feathers and wraps its wings round whoever it strikes. | where the target stood: can be dodged |
| 329 | Transcendent Sword | 461 Omnimon | `finishers_dash_b` | The Grey Sword lights: a blade of blue-white light with written signs burning orange along it grows from Omnimon across the field and through the target. | one enemy |

## Composed effects

No species plays a composed effect now: all imported finishers are authored. This section says how the tool
works.

A species with no DW2 technique to convert gets a composed effect: one of the disc's own chunks (its template)
with a look of its own. `tools/efecompose.py` copies the template and changes only its texture (pictures copied
from other disc chunks), its colours and its model's size. The script, its variables, the launch table and the timing stay byte for byte, so the technique plays,
travels and hits exactly as the template does. The chunk is built at derive time from the player's disc, like
every other chunk here; nothing of the disc is committed.

An entry of the kind the tool reads (no entry in `content/battle/own-effects.json` is one now):

```json
"162": {"name": "Nightmare Shock", "stands_for": 62,
        "compose": {"recolour": {"ramp": ["#14001e", "#5a1494", "#c870ff", "#f4dcff"]}, "scale": 1.3},
        "check": {"hue": 280}}
```

- `stands_for`: the template, a disc chunk (0-121). It is the chunk of the finisher the species' technique uses
  (the technique's effect id less 0x100), so the launch point and the hit stay those the technique was balanced
  with. Use the technique the species keeps as its finisher (the last of its `techniques`).
- `compose.recolour`: the new colours of every palette colour of the template's texture, and of the colour
  vectors its script hands the engine (sprite tints, model colours).
  - `"ramp"`: two or more colours from dark to bright. Each colour takes the ramp's colour at its own brightness.
    Effects blend additively, so the brightest end is what reads; keep it light.
  - `"hue"`: degrees (0 red, 120 green, 240 blue), each colour turned to that hue, with `"saturation"` as a floor
    (0-1, default 0.6).
  - `"rows"`: only these palette rows (default all).
  - Colour 0 stays transparent, the semi-transparency bit stays, and no visible colour becomes 0.
- `compose.texture`: a list of texel rectangles copied over the template's texture before the recolour, each
  `{"from": chunk, "rect": [u, v, w, h], "to": [u, v], "palettes": [[from row, to row]]}` (`to` defaults to the
  same place; u and w even). It gives the template's sprites or faces a new picture: Poison Cobweb's breath
  sprites draw chunk 105's web. Which rectangle a template's sprites use is in the simulation's sprites
  (`u, v, w, h` and the palette row) and its prims' UVs. The texture is uploaded to video memory and not kept,
  so this costs no battle memory.
- `compose.scale`: the template's 3D model resized, one factor or `[x, y, z]`. Sprites keep their size. 1.2-1.5
  makes a template read as a different, heavier technique; the hit test does not change.
- `check.hue`: the main hue the effect must show, for the check.

The species JSON then names the chunk: `"own_effect": {"technique": "Death Claw", "chunk": 162}`, the technique
being the template's.

Engine effects that a script asks for by number (clouds, flashes, particle emitters, screen sprites) are drawn
by the engine with its own colours: a composition cannot recolour them. The check lists them.

### Making one

1. Read the design's `look` (the technique's design). When the template's picture does not fit it (a cloud for a
   web), find a disc chunk whose texture has the right one and copy it with `texture`. Then pick the colours. Pick a ramp whose dark end is nearly
   black and whose bright end is the look's colour almost white.
2. Chunks 162-195 were the composed effects' range. No chunk of it is used now.
3. Add the entry and the species' `own_effect`, then render the sheet and look at it:
   `python -m tools.efecompose sheet KEY --out SHEET.png`. The template's frames are above, the composed ones
   below, at the same ticks, each column cropped around what either draws at that tick. The composed row must read as the look and not as a
   recoloured copy of the template: if it does not, change the ramp or the scale.
4. Check it: `python -m tools.efecheck --composed KEY`. Its `distinct` measure counts any change of colour, so a
   plain recolour passes it: only the sheet tells whether the effect reads as its own. It runs the template and the composed chunk through
   `tools/efesim.py` (no DW2 disc) and fails when:
   - **the technique changed**: a byte changed outside the palette, the copied texels, the model's vertices and the
     script colours,
     the launch table differs, or the run's draws, sprites, hits, hit tests or sounds differ from the template's;
   - **it is empty**: per phase (cast before the first hit, hit after; one phase when the simulation deals none)
     the energy or the coverage of the frames is under 0.35 of the template's, or the box (median diagonal over
     the lit frames) is outside 0.5-3 times the template's;
   - **the hue is off**: the main hue (the chroma-weighted circular mean over the pixels with saturation over 0.25)
     is more than 35 degrees from `check.hue`;
   - **it is the template**: the summed RGB difference of all frames is under 0.25 of their summed RGB.
5. `python -m unittest tools.test_efecompose` checks every composed entry too.

### Imports that keep their template

None now. Eleven imported finishers once kept the DW1 effect they replace (Tinmon, Paildramon, Shakkoumon,
Devidramon, Gatomon, DemiDevimon, Sorcermon, Infermon, MarineAngemon, VioletElecmon and Tylomon): their source
did not convert. Each plays an authored effect now, as every other imported species does.

A sheet and a check take about 15 seconds. The chunk keeps the template's size, so the memory the battle keeps is
the template's.

The chunk's data (every effect, whatever its source) lives in the battle's effect heap (0x41000 bytes), loaded with the battle's other effects: up to
16 chunks, 4 fighters x 4 techniques. The main executable grows by 112 B: `getSpeciesTechEffect`'s
140 less 28 its two resident call sites save (the patches after it, which call `digimonPara`, `raiseRow`
and the evolution rows out of line, give 2,656 B back).

Validation: `python3 -m unittest tools.test_technique_effects` builds every authored effect and runs its chunk in
`tools/efesim.py`, a model of the effect script interpreter: it ends, sounds, draws, and hits what its technique
hits (one enemy, or all of them), and the ones that fly to where the target stood miss a target that walks away.
