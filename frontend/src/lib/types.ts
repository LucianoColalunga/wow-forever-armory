/** Tipos de las respuestas de la API (subconjunto usado por la interfaz). */

export type Dataset = "real" | "demo";

export interface DataMeta {
  dataset: Dataset;
  is_demo: boolean;
  data_version: number;
  last_processed_at: string | null;
  stale: boolean;
  generated_at: string;
}

export interface Paged<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  meta: DataMeta | null;
}

export interface GuildRef {
  id: number;
  name: string;
  realm: string;
  region: string;
  faction: string | null;
}

export interface Character {
  id: number;
  name: string;
  realm: string;
  region: string;
  class_slug: string | null;
  spec: string | null;
  class_source: string;
  class_confidence: number;
  faction: string | null;
  guild: GuildRef | null;
  guild_source: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  dataset: Dataset;
  fights?: number;
  membership?: string;
}

export interface Instance {
  id: number;
  slug: string;
  name: string;
  kind: "raid" | "dungeon" | "battleground";
  max_players: number | null;
  verification: string;
  source_url: string;
  is_new: boolean;
  level_range: string | null;
  notes: string;
}

export interface Encounter {
  id: number;
  game_encounter_id: number;
  name: string;
  instance_id: number | null;
  dataset: Dataset;
}

export interface FightSummary {
  id: number;
  kind: "encounter" | "dungeon_run" | "battleground";
  encounter: Encounter | null;
  instance: Instance | null;
  difficulty_id: number | null;
  group_size: number | null;
  success: boolean | null;
  start_at: string;
  duration_ms: number;
  zone_name: string | null;
  rankable: boolean;
  unrankable_reason: string | null;
  duplicate_of_id: number | null;
  boss_min_hp_pct: number | null;
  player_count: number;
  report_public_id: string;
  dataset: Dataset;
  first_line?: number;
  last_line?: number;
}

export interface Participant {
  character_id: number;
  name: string;
  realm: string;
  class_slug: string | null;
  spec: string | null;
  role: string;
  damage_done: number;
  effective_damage: number;
  overkill: number;
  damage_absorbed_by_target: number;
  damage_to_players: number;
  healing_gross: number;
  healing_effective: number;
  overhealing: number;
  heal_absorbed: number;
  absorbs_provided: number;
  damage_taken: number;
  damage_taken_absorbed: number;
  deaths: number;
  interrupts: number;
  dispels: number;
  killing_blows: number;
  time_alive_ms: number;
  dps: number;
  hps: number;
  aps: number;
  dtps: number;
  survival_pct: number;
  abilities?: { damage: { name: string; amount: number }[]; healing: { name: string; amount: number }[] } | null;
  death_log?: { t_ms: number; ability: string | null; killer: string | null }[] | null;
  avg_item_level?: number | null;
  gear?: GearItem[] | null;
  casts?: CastTimelineData | null;
}

export interface GearItem {
  slot: number;
  slot_name: string;
  item_id: number;
  item_level: number;
  enchants: number[];
  bonus_ids: number[];
  gems: number[];
}

/** Línea de tiempo compacta: nombres de hechizos y, por lanzamiento, ms y el índice del hechizo. */
export interface CastTimelineData {
  spells: string[];
  t: number[];
  s: number[];
}

export interface Timeline {
  bucket_ms: number;
  buckets: number;
  raid_damage: number[];
  raid_healing: number[];
  players_damage: Record<string, number[]>;
  players_healing: Record<string, number[]>;
}

export interface FightDetail extends FightSummary {
  participants: Participant[];
  timeline: Timeline | null;
  issues: { severity: string; code: string; message: string; line_no: number | null }[];
  source: {
    report_public_id: string;
    report_title: string;
    file_sha256: string | null;
    file_name: string | null;
    first_line: number;
    last_line: number | null;
    parser_version: string;
  };
}

export interface RankingRow {
  rank: number;
  value: number;
  raw_value?: number;
  samples: number;
  partitions?: number;
  stddev?: number;
  bucket_n?: number;
  fight_id?: number;
  report_id?: number;
  occurred_at: string;
  class_slug?: string | null;
  spec?: string | null;
  role?: string;
  duration_ms?: number;
  character_id: number;
  name: string;
  realm: string;
  region: string;
  character_class: string | null;
  character_spec: string | null;
  guild_id: number | null;
  guild_name: string | null;
}

export interface RankingMeta {
  records_used: number;
  records_excluded: number;
  characters: number;
  period_from: string | null;
  period_to: string | null;
  higher_better: boolean;
  method: string;
  method_label: string;
  method_description: string;
  metric: string;
  metric_label: string;
  min_bucket_size?: number;
  consistency_min_kills?: number;
  consistency_last_n?: number;
  difficulty_id?: number | null;
  group_size?: number | null;
  scale?: string;
  partial_data_note?: string;
}

export interface RankingResponse {
  rows: RankingRow[];
  total: number;
  page: number;
  page_size: number;
  meta: RankingMeta;
  data: DataMeta;
  cache?: string;
}

export interface Season {
  id: number;
  slug: string;
  name: string;
  kind: string;
  starts_at: string;
  ends_at: string | null;
  is_official: boolean;
  source_note: string;
}

export interface SourceInfo {
  key: string;
  label: string;
  status: string;
  verified: boolean;
  provides: string[];
  description: string;
  limits: string;
  references: string[];
}

export interface PvpMode {
  key: string;
  label: string;
  status: string;
  detail: string;
}

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: "admin" | "uploader";
  is_active: boolean;
}
