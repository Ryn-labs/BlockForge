// Block colours and shapes for the 3D preview.
const DYES = {
  white: 0xe9ecec, orange: 0xf07613, magenta: 0xbd44b3, light_blue: 0x3aafd9, yellow: 0xf8c627, lime: 0x70b919,
  pink: 0xed8dac, gray: 0x3e4447, light_gray: 0x8e8e86, cyan: 0x158991, purple: 0x792aac, blue: 0x35399d,
  brown: 0x724728, green: 0x546d1b, red: 0xa12722, black: 0x141519,
};
const CONCRETE = {
  white: 0xcfd5d6, orange: 0xe06100, magenta: 0xa9309f, light_blue: 0x2389c6, yellow: 0xf1af15, lime: 0x5ea818,
  pink: 0xd5658e, gray: 0x36393d, light_gray: 0x7d7d73, cyan: 0x157788, purple: 0x64209c, blue: 0x2c2e8f,
  brown: 0x603b1f, green: 0x495b24, red: 0x8e2020, black: 0x080a0f,
};
const TERRACOTTA = {
  white: 0xd1b2a1, orange: 0xa05325, magenta: 0x95586c, light_blue: 0x706c8a, yellow: 0xba8523, lime: 0x677534,
  pink: 0xa04d4e, gray: 0x392a23, light_gray: 0x876a61, cyan: 0x575b5b, purple: 0x7a4958, blue: 0x4a3b5b,
  brown: 0x4d3323, green: 0x4c532a, red: 0x8f3d2e, black: 0x251610,
};
const WOOD = {
  oak: [0xa2834f, 0x6d5532], spruce: [0x725430, 0x3b2912], birch: [0xc0af79, 0xd8d7d2], jungle: [0xa07351, 0x554419],
  acacia: [0xa85a32, 0x676157], dark_oak: [0x42291a, 0x3c2e1a], mangrove: [0x773636, 0x5a4a2d],
  cherry: [0xe2b2aa, 0x37212a], pale_oak: [0xe5dcd8, 0x6d6460], bamboo: [0xc4af51, 0x8a9a37],
  crimson: [0x653147, 0x5c1a1e], warped: [0x2b6963, 0x3a3b4e],
};
const FIXED = {
  stone: 0x7e7e7e, cobblestone: 0x7a7a7a, mossy_cobblestone: 0x6e775f, stone_bricks: 0x7a7979,
  mossy_stone_bricks: 0x737a62, cracked_stone_bricks: 0x767676, chiseled_stone_bricks: 0x777777, smooth_stone: 0x9e9e9e,
  andesite: 0x888888, polished_andesite: 0x848786, diorite: 0xbcbcbc, polished_diorite: 0xc1c1c3, granite: 0x956755,
  polished_granite: 0x9a6a59, deepslate: 0x505053, cobbled_deepslate: 0x4d4d51, polished_deepslate: 0x484849,
  deepslate_bricks: 0x464646, cracked_deepslate_bricks: 0x404040, deepslate_tiles: 0x363637, cracked_deepslate_tiles: 0x343434,
  chiseled_deepslate: 0x363636, tuff: 0x6c6d66, polished_tuff: 0x626866, tuff_bricks: 0x62665f, chiseled_tuff: 0x5c605a,
  calcite: 0xdfe0dc, dripstone_block: 0x866b5c, blackstone: 0x2a2328, polished_blackstone: 0x35303b,
  polished_blackstone_bricks: 0x302a32, cracked_polished_blackstone_bricks: 0x2c2529, gilded_blackstone: 0x382b26,
  basalt: 0x505055, polished_basalt: 0x636366, smooth_basalt: 0x48484e, bricks: 0x966153, mud_bricks: 0x89684f,
  packed_mud: 0x8e6b50, mud: 0x3c393d, dirt: 0x866043, coarse_dirt: 0x775538, rooted_dirt: 0x90674c, podzol: 0x5c3f18,
  grass_block: 0x6a9b3e, dirt_path: 0x947a41, farmland: 0x52341b, mycelium: 0x6f6265, moss_block: 0x596d2d,
  moss_carpet: 0x596d2d, sand: 0xdbcfa3, red_sand: 0xbe6621, gravel: 0x837f7e, clay: 0xa0a6b3, sandstone: 0xd8cb9b,
  cut_sandstone: 0xd9ce9f, smooth_sandstone: 0xe0d6aa, chiseled_sandstone: 0xd8ca9b, red_sandstone: 0xb5621f,
  cut_red_sandstone: 0xbd6520, smooth_red_sandstone: 0xb5621f, terracotta: 0x985e43, snow_block: 0xf9fefe, snow: 0xf9fefe,
  powder_snow: 0xf8fdfd, ice: 0x91b7fd, packed_ice: 0x8db4fa, blue_ice: 0x74a8fd, obsidian: 0x0f0b19,
  crying_obsidian: 0x200a3c, netherrack: 0x612626, nether_bricks: 0x2c1519, red_nether_bricks: 0x450709,
  cracked_nether_bricks: 0x281417, chiseled_nether_bricks: 0x2f171b, nether_wart_block: 0x720b0b, warped_wart_block: 0x167679,
  soul_sand: 0x513e32, soul_soil: 0x4b3a2e, glowstone: 0xfbda74, shroomlight: 0xf09a4b, sea_lantern: 0xacc7be,
  magma_block: 0x8e3f1f, end_stone: 0xdbde9e, end_stone_bricks: 0xdae0a2, purpur_block: 0xa97ea9, purpur_pillar: 0xab81ab,
  prismarine: 0x639c97, prismarine_bricks: 0x63ab9e, dark_prismarine: 0x335b4b, quartz_block: 0xebe5de,
  smooth_quartz: 0xece6df, quartz_bricks: 0xeae4dd, quartz_pillar: 0xebe6e0, chiseled_quartz_block: 0xe7e2da,
  amethyst_block: 0x8562bf, budding_amethyst: 0x8462bf, copper_block: 0xc06c50, cut_copper: 0xbf6b51,
  exposed_copper: 0xa17e68, exposed_cut_copper: 0x9b7a65, weathered_copper: 0x6c996e, weathered_cut_copper: 0x6d9170,
  oxidized_copper: 0x52a385, oxidized_cut_copper: 0x4f997e, iron_block: 0xdcdcdc, gold_block: 0xf6d03d,
  diamond_block: 0x62ede4, emerald_block: 0x2acb57, lapis_block: 0x1f438c, redstone_block: 0xaf1805, coal_block: 0x101010,
  netherite_block: 0x423d3f, raw_iron_block: 0xa6876b, raw_gold_block: 0xdda92e, raw_copper_block: 0x9a6a4f,
  bookshelf: 0x6f5a3b, chiseled_bookshelf: 0x6f5a3b, crafting_table: 0x77583a, furnace: 0x6e6e6e, blast_furnace: 0x515051,
  smoker: 0x56493b, barrel: 0x8a6538, chest: 0xa77a32, trapped_chest: 0xa77a32, ender_chest: 0x253537,
  hay_block: 0xa68b0c, pumpkin: 0xc6761c, carved_pumpkin: 0xc6761c, jack_o_lantern: 0xd6902a, melon: 0x6f9123,
  sponge: 0xc4c04a, slime_block: 0x6fc05a, honey_block: 0xfbb931, honeycomb_block: 0xe5941e, bone_block: 0xe1ddc9,
  target: 0xe2aa9e, note_block: 0x58392a, jukebox: 0x5e402e, tnt: 0xb5462c, beacon: 0x75dcd7, lantern: 0xf4bd5d,
  soul_lantern: 0x5ec7d1, torch: 0xffd36b, wall_torch: 0xffd36b, soul_torch: 0x6ed8e3, redstone_torch: 0xd33a1a,
  campfire: 0xf0a040, soul_campfire: 0x5ec7d1, chain: 0x3f4553, iron_bars: 0x8b8d8d, lightning_rod: 0xc06c50,
  bell: 0xf3c13b, anvil: 0x444444, cauldron: 0x3f3f3f, water_cauldron: 0x3f3f3f, grindstone: 0x8c8c8c,
  stonecutter: 0x7b7672, lectern: 0xa47f4c, loom: 0x8e7656, cartography_table: 0x5a4433, fletching_table: 0xb8a774,
  smithing_table: 0x3a3b47, enchanting_table: 0x5e1d1e, brewing_stand: 0x7a6a50, flower_pot: 0x7c4536,
  water: 0x3f76e4, lava: 0xd46b17, glass: 0xc6e2ea, glass_pane: 0xc6e2ea, tinted_glass: 0x2c272f,
  short_grass: 0x6a9b3e, tall_grass: 0x6a9b3e, fern: 0x5d8a3a, large_fern: 0x5d8a3a, dead_bush: 0x7b5b2b,
  vine: 0x3f7d22, glow_lichen: 0x70827a, sugar_cane: 0x93c05a, bamboo: 0x6f9a2c, cactus: 0x5a8a2c, kelp: 0x5a8a2c,
  lily_pad: 0x2a7d33, poppy: 0xc0262a, dandelion: 0xf2d43a, cornflower: 0x4a6be0, allium: 0xb57ae0,
  azure_bluet: 0xd8e4f0, blue_orchid: 0x2aa7e0, oxeye_daisy: 0xe9ecd8, lily_of_the_valley: 0xf0f0f0,
  red_tulip: 0xd03a2a, orange_tulip: 0xe07a2a, white_tulip: 0xe8e8e8, pink_tulip: 0xe8a0c0, sunflower: 0xf6c62a,
  rose_bush: 0xb52a2a, peony: 0xe0a8d8, lilac: 0xc49ad0, wither_rose: 0x2a2a20, torchflower: 0xe28a3a,
  pink_petals: 0xf3a6c8, spore_blossom: 0xd66a9a, azalea: 0x667f30, flowering_azalea: 0x8c6f9a, sweet_berry_bush: 0x3a6a2a,
  brown_mushroom: 0x997257, red_mushroom: 0xd83a2f, brown_mushroom_block: 0x957051, red_mushroom_block: 0xc82f2c,
  mushroom_stem: 0xcbc4b9, cobweb: 0xe4e8ea, scaffolding: 0xae8b4e, ladder: 0x7f6438, rail: 0x7f7563,
  powered_rail: 0x9a7e44, sculk: 0x0d1d24, sculk_sensor: 0x085a5f, ochre_froglight: 0xf6e9a5,
  verdant_froglight: 0xe5f4e2, pearlescent_froglight: 0xf4e9ee, resin_block: 0xd6681a, resin_bricks: 0xc85a16,
  copper_bulb: 0xc06c50, crafter: 0x6e6262, decorated_pot: 0x8c4e3e, candle: 0xe7d5b0, white_candle: 0xe0e3e3,
  respawn_anchor: 0x2b1f43, lodestone: 0x7a7b7e, structure_void: 0xffffff, barrier: 0xff0000, light: 0xffff99,
  bedrock: 0x555555, sea_pickle: 0x6b7a31, coral_block: 0x3150c8, dried_kelp_block: 0x323b29, cherry_leaves: 0xe9a3c4,
  azalea_leaves: 0x5b7a2e, flowering_azalea_leaves: 0x76784a, pale_oak_leaves: 0x8b938a, mangrove_roots: 0x4a3a28,
  muddy_mangrove_roots: 0x463b2d, pale_moss_block: 0x6b746a, pale_moss_carpet: 0x6b746a, creaking_heart: 0x4f4642,
  heavy_core: 0x50525a, trial_spawner: 0x2f4552, vault: 0x3a4448, spawner: 0x2a3a48, end_rod: 0xf0e8e0,
  conduit: 0x9a8a6a, dragon_egg: 0x0c0910, player_head: 0x6e4b30, skeleton_skull: 0xc8c8c8, armor_stand: 0x9a7a4a,
  redstone_wire: 0xb01208, repeater: 0xa9a49e, comparator: 0xb3aca5, observer: 0x5f5f5f, piston: 0x9d8a68,
  sticky_piston: 0x7fa060, redstone_lamp: 0x8a5a33, hopper: 0x3e3e42, dropper: 0x707070, dispenser: 0x6d6d6d,
  daylight_detector: 0xc2ad86, lever: 0x6e5a3c, tripwire_hook: 0x8a7b6a, detector_rail: 0x8a7563, activator_rail: 0x8a6a5e,
  redstone_ore: 0x8a6b6b, note_block: 0x58392a, sculk_sensor: 0x0d5a63, crafter: 0x6e6262,
};
const LEAF = { oak: 0x4a7a26, spruce: 0x3d5e3d, birch: 0x6a8b3e, jungle: 0x3f8a1e, acacia: 0x5f8a1e,
  dark_oak: 0x3c6a1e, mangrove: 0x5a8a2a };

const cache = new Map();
export function blockColor(state) {
  const name = state.split('[')[0].replace('minecraft:', '');
  if (cache.has(name)) return cache.get(name);
  const c = computeColor(name);
  cache.set(name, c);
  return c;
}

function dyeOf(name) {
  for (const d of ['light_blue', 'light_gray', ...Object.keys(DYES)]) if (name.startsWith(d + '_')) return d;
  return null;
}

function computeColor(name) {
  if (FIXED[name] !== undefined) return FIXED[name];
  const dye = dyeOf(name);
  if (dye) {
    if (name.includes('concrete_powder')) return lighten(CONCRETE[dye], 0.12);
    if (name.includes('concrete')) return CONCRETE[dye];
    if (name.includes('glazed_terracotta')) return lighten(TERRACOTTA[dye], 0.15);
    if (name.includes('terracotta')) return TERRACOTTA[dye];
    if (name.includes('stained_glass')) return DYES[dye];
    if (name.includes('candle')) return DYES[dye];
    return DYES[dye];   // wool, carpet, bed, banner, shulker
  }
  if (name.startsWith('potted_')) return FIXED.flower_pot;
  if (name.endsWith('_leaves')) { for (const w in LEAF) if (name.startsWith(w)) return LEAF[w]; return 0x4a7a26; }
  for (const w of ['dark_oak', 'pale_oak', ...Object.keys(WOOD)]) {
    if (name.includes(w)) {
      const [plank, bark] = WOOD[w];
      if (name.startsWith('stripped_')) return plank;
      if (/_(log|wood|stem|hyphae)$/.test(name)) return bark;
      return plank;
    }
  }
  if (name.includes('mossy')) return 0x6e775f;
  // strip shape suffixes and retry (e.g. stone_brick_stairs -> stone_bricks)
  const base = name.replace(/_(stairs|slab|wall|fence|fence_gate|pressure_plate|button|trapdoor|door)$/, '');
  for (const cand of [base, base + 's', base + '_block', base.replace('brick', 'bricks'), base.replace('tile', 'tiles'),
    base.replace(/^waxed_/, ''), base.replace(/^waxed_/, '') + '_block', base.replace('smooth_', '')]) {
    if (cand !== name && FIXED[cand] !== undefined) return FIXED[cand];
  }
  if (name.includes('copper')) return name.includes('oxidized') ? 0x52a385 : name.includes('weathered') ? 0x6c996e : name.includes('exposed') ? 0xa17e68 : 0xc06c50;
  if (name.includes('quartz')) return 0xebe5de;
  if (name.includes('sandstone')) return name.includes('red') ? 0xb5621f : 0xd8cb9b;
  if (name.includes('blackstone')) return 0x302a32;
  if (name.includes('deepslate')) return 0x464646;
  if (name.includes('prismarine')) return 0x63ab9e;
  if (name.includes('nether')) return 0x2c1519;
  if (name.includes('purpur')) return 0xa97ea9;
  if (name.includes('end_stone')) return 0xdae0a2;
  if (name.includes('ore')) return 0x7e7e7e;
  if (name.includes('coral')) return 0xc84a7a;
  if (name.includes('tulip') || name.includes('flower')) return 0xd85a7a;
  if (name.includes('iron')) return 0xa8a8a8;
  if (name.includes('stone')) return 0x7e7e7e;
  // unknown: stable mid-tone from the name
  let h = 0; for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return ((96 + (h & 63)) << 16) | ((96 + ((h >> 6) & 63)) << 8) | (96 + ((h >> 12) & 63));
}

function lighten(c, f) {
  const r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255;
  const L = v => Math.min(255, Math.round(v + (255 - v) * f));
  return (L(r) << 16) | (L(g) << 8) | L(b);
}

// ---------------------------------------------------------------- shapes
// kind: 'full' (opaque cube, culls neighbours), 'glass' (transparent cube), 'water', or 'boxes'
const PLANT = /(sapling|_flower$|^poppy|dandelion|tulip|orchid|allium|bluet|daisy|cornflower|lily_of|wither_rose|torchflower|short_grass|^fern$|tall_grass|large_fern|dead_bush|mushroom$|sweet_berry|sugar_cane|^bamboo$|kelp|seagrass|vine|lichen|roots$|sprouts|fungus|petals|sunflower|lilac|rose_bush|peony|pitcher|cobweb|azalea$|_coral$|_coral_fan|^wheat|carrots|potatoes|beetroots|nether_wart$|eyeblossom|bush$|dripleaf|spore_blossom|hanging_roots|cave_vines)/;

export function parseProps(state) {
  const i = state.indexOf('[');
  const p = {};
  if (i < 0) return p;
  for (const kv of state.slice(i + 1, -1).split(',')) { const [k, v] = kv.split('='); p[k] = v; }
  return p;
}

export function shapeOf(state) {
  const name = state.split('[')[0].replace('minecraft:', '');
  const p = parseProps(state);
  if (name === 'water' || name === 'bubble_column') return { kind: 'water' };
  if (name === 'lava') return { kind: 'full' };
  if (name.includes('glass') && !name.includes('pane')) return { kind: 'glass' };
  if (name === 'ice' || name === 'slime_block' || name === 'honey_block') return { kind: 'glass' };
  if (name === 'barrier' || name === 'structure_void' || name === 'light') return { kind: 'skip' };
  if (name === 'redstone_wire') {
    const t = 0.0625, w = 0.19, boxes = [[0.5 - w / 2, 0, 0.5 - w / 2, 0.5 + w / 2, t, 0.5 + w / 2]];
    if (p.north && p.north !== 'none') boxes.push([0.5 - w / 2, 0, 0, 0.5 + w / 2, t, 0.5]);
    if (p.south && p.south !== 'none') boxes.push([0.5 - w / 2, 0, 0.5, 0.5 + w / 2, t, 1]);
    if (p.west && p.west !== 'none') boxes.push([0, 0, 0.5 - w / 2, 0.5, t, 0.5 + w / 2]);
    if (p.east && p.east !== 'none') boxes.push([0.5, 0, 0.5 - w / 2, 1, t, 0.5 + w / 2]);
    if (p.north === 'up') boxes.push([0.5 - w / 2, 0, 0, 0.5 + w / 2, 1, t]);
    if (p.south === 'up') boxes.push([0.5 - w / 2, 0, 1 - t, 0.5 + w / 2, 1, 1]);
    if (p.west === 'up') boxes.push([0, 0, 0.5 - w / 2, t, 1, 0.5 + w / 2]);
    if (p.east === 'up') boxes.push([1 - t, 0, 0.5 - w / 2, 1, 1, 0.5 + w / 2]);
    return { kind: 'boxes', boxes };
  }
  if (name === 'repeater' || name === 'comparator') {
    // base slab plus two little torches lined up along the signal direction
    const ns = (p.facing === 'north' || p.facing === 'south');
    const a = ns ? [[.44, .125, .2, .56, .45, .32], [.44, .125, .68, .56, .45, .8]] : [[.2, .125, .44, .32, .45, .56], [.68, .125, .44, .8, .45, .56]];
    return { kind: 'boxes', boxes: [[0, 0, 0, 1, .125, 1], ...a] };
  }
  if (name === 'daylight_detector') return { kind: 'boxes', boxes: [[0, 0, 0, 1, .375, 1]] };
  if (name === 'lever') return { kind: 'boxes', boxes: [[.3, 0, .25, .7, .2, .75], [.45, .1, .45, .55, .65, .55]] };
  if (name === 'hopper') return { kind: 'boxes', boxes: [[0, .625, 0, 1, 1, 1], [.25, .25, .25, .75, .625, .75], [.375, 0, .375, .625, .25, .625]] };
  if (name === 'tripwire_hook') return { kind: 'boxes', boxes: [[.4, .3, .4, .6, .8, .6]] };
  if (name === 'tripwire') return { kind: 'boxes', boxes: [[0, .05, .47, 1, .08, .53]] };
  if (name.endsWith('_slab')) {
    if (p.type === 'double') return { kind: 'full' };
    return { kind: 'boxes', boxes: [p.type === 'top' ? [0, .5, 0, 1, 1, 1] : [0, 0, 0, 1, .5, 1]] };
  }
  if (name.endsWith('_stairs')) {
    const top = p.half === 'top';
    const base = top ? [0, .5, 0, 1, 1, 1] : [0, 0, 0, 1, .5, 1];
    const y0 = top ? 0 : .5, y1 = top ? .5 : 1;
    const step = { east: [.5, y0, 0, 1, y1, 1], west: [0, y0, 0, .5, y1, 1], south: [0, y0, .5, 1, y1, 1],
      north: [0, y0, 0, 1, y1, .5] }[p.facing || 'north'];
    return { kind: 'boxes', boxes: [base, step] };
  }
  if (name.endsWith('carpet') || name.endsWith('pressure_plate') || name.includes('rail') || name === 'snow' ||
      name === 'lily_pad' || name === 'pink_petals' || name === 'redstone_wire' || name.endsWith('_petals'))
    return { kind: 'boxes', boxes: [[0, 0, 0, 1, name === 'snow' ? .125 * (+p.layers || 1) : .0625, 1]] };
  if (name.endsWith('_trapdoor')) {
    if (p.open === 'true') {
      const f = p.facing || 'north';
      return { kind: 'boxes', boxes: [{ north: [0, 0, .8125, 1, 1, 1], south: [0, 0, 0, 1, 1, .1875],
        east: [0, 0, 0, .1875, 1, 1], west: [.8125, 0, 0, 1, 1, 1] }[f]] };
    }
    return { kind: 'boxes', boxes: [p.half === 'top' ? [0, .8125, 0, 1, 1, 1] : [0, 0, 0, 1, .1875, 1]] };
  }
  if (name.endsWith('_door')) {
    const f = p.facing || 'north';
    return { kind: 'boxes', boxes: [{ north: [0, 0, .8125, 1, 1, 1], south: [0, 0, 0, 1, 1, .1875],
      east: [0, 0, 0, .1875, 1, 1], west: [.8125, 0, 0, 1, 1, 1] }[f]] };
  }
  if (name.endsWith('_fence') || name.endsWith('_wall') || name.endsWith('pane') || name === 'iron_bars' ||
      name.endsWith('_fence_gate'))
    return { kind: 'connect', post: name.endsWith('_wall') ? .25 : name.endsWith('_fence') ? .375 : .4375,
      arm: name.endsWith('_wall') ? .3125 : name.endsWith('_fence') ? .4375 : .4375, wall: name.endsWith('_wall') };
  if (name.endsWith('_bed')) return { kind: 'boxes', boxes: [[0, 0, 0, 1, .5625, 1]] };
  if (name.endsWith('_sign') || name.endsWith('_banner')) return { kind: 'boxes', boxes: [[.25, 0, .4375, .75, .9, .5625]] };
  if (name.endsWith('_button')) return { kind: 'boxes', boxes: [[.3125, .375, .3125, .6875, .625, .6875]] };
  if (name.includes('torch') || name === 'end_rod' || name === 'lightning_rod' || name === 'chain' || name.includes('candle'))
    return { kind: 'boxes', boxes: [[.4375, 0, .4375, .5625, name.includes('candle') ? .4 : .65, .5625]] };
  if (name.includes('lantern') && !name.includes('jack') && name !== 'sea_lantern')
    return { kind: 'boxes', boxes: [[.3125, p.hanging === 'true' ? .0625 : 0, .3125, .6875, p.hanging === 'true' ? .5625 : .5, .6875]] };
  if (name.startsWith('potted_') || name === 'flower_pot') return { kind: 'boxes', boxes: [[.3125, 0, .3125, .6875, .375, .6875], [.4, .375, .4, .6, .75, .6]] };
  if (name === 'ladder') return { kind: 'boxes', boxes: [[0, 0, .875, 1, 1, 1]] };
  if (name.endsWith('campfire')) return { kind: 'boxes', boxes: [[0, 0, 0, 1, .4375, 1]] };
  if (name.endsWith('_head') || name.endsWith('_skull')) return { kind: 'boxes', boxes: [[.25, 0, .25, .75, .5, .75]] };
  if (name === 'bell' || name === 'brewing_stand' || name === 'decorated_pot' || name === 'sea_pickle')
    return { kind: 'boxes', boxes: [[.25, 0, .25, .75, .75, .75]] };
  if (name === 'cactus' ) return { kind: 'boxes', boxes: [[.0625, 0, .0625, .9375, 1, .9375]] };
  if (name === 'lectern' || name === 'enchanting_table') return { kind: 'boxes', boxes: [[0, 0, 0, 1, .75, 1]] };
  if (name === 'stonecutter') return { kind: 'boxes', boxes: [[0, 0, 0, 1, .5625, 1]] };
  if (name === 'anvil' || name === 'grindstone') return { kind: 'boxes', boxes: [[.125, 0, .125, .875, 1, .875]] };
  if (name.endsWith('chest')) return { kind: 'boxes', boxes: [[.0625, 0, .0625, .9375, .875, .9375]] };
  if (name === 'scaffolding') return { kind: 'boxes', boxes: [[0, .875, 0, 1, 1, 1], [0, 0, 0, .125, 1, .125], [.875, 0, 0, 1, 1, .125], [0, 0, .875, .125, 1, 1], [.875, 0, .875, 1, 1, 1]] };
  if (PLANT.test(name) || name.startsWith('tall_') || name.endsWith('_sapling'))
    return { kind: 'plant' };
  return { kind: 'full' };
}
