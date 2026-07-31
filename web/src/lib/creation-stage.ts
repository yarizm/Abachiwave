import {
  ArrangementPlanVersion,
  AudioDemoVersion,
  AssetTree,
  ChordProgressionVersion,
  ExportBundle,
  LyricsVersion,
  MidiAssetVersion,
} from "@/lib/composition";
import { IdeaIntake, SongSpecVersion } from "@/lib/song-specs";

/**
 * Creation Chain — the linear path a creator walks from idea to exportable asset.
 * Each step maps to a workspace panel and is derived purely from the workspace
 * snapshot (no independent hand-written state), so it can never drift from real
 * assets.
 */
export type CreationStepId =
  | "idea"
  | "song_spec"
  | "approve"
  | "composition"
  | "arrangement"
  | "demo"
  | "export";

export type CreationStepStatus = "done" | "active" | "blocked" | "todo";

export type CreationStep = {
  id: CreationStepId;
  status: CreationStepStatus;
  /** anchor id of the corresponding panel, for scroll-to navigation */
  anchor: string;
};

export type CreationStage = {
  /** index of the current (active) step, -1 when all done */
  currentIndex: number;
  steps: CreationStep[];
  /** true once every step is done */
  complete: boolean;
};

export type CreationStageInput = {
  latestIntake: IdeaIntake | null;
  versions: SongSpecVersion[];
  lyricsVersions: LyricsVersion[];
  chordVersions: ChordProgressionVersion[];
  midiAssets: MidiAssetVersion[];
  arrangementVersions: ArrangementPlanVersion[];
  assetTree: AssetTree | null;
  demoVersions: AudioDemoVersion[];
  exportBundles: ExportBundle[];
};

const STEP_ORDER: { id: CreationStepId; anchor: string }[] = [
  { id: "idea", anchor: "song-spec-panel" },
  { id: "song_spec", anchor: "song-spec-panel" },
  { id: "approve", anchor: "song-spec-panel" },
  { id: "composition", anchor: "composition-panel" },
  { id: "arrangement", anchor: "delivery-panel" },
  { id: "demo", anchor: "demo-panel" },
  { id: "export", anchor: "delivery-panel" },
];

function hasApprovedSongSpec(versions: SongSpecVersion[]): boolean {
  return versions.some((version) => version.status === "approved");
}

function hasDraftSongSpec(versions: SongSpecVersion[]): boolean {
  return versions.length > 0;
}

function hasComposition(input: CreationStageInput): boolean {
  const tree = input.assetTree?.current;
  if (!tree) {
    return (
      input.lyricsVersions.length > 0 ||
      input.chordVersions.length > 0 ||
      input.midiAssets.length > 0
    );
  }
  return Boolean(tree.lyrics || tree.chords || tree.midi_assets.length > 0);
}

function hasArrangement(input: CreationStageInput): boolean {
  return input.arrangementVersions.length > 0;
}

function hasDemo(input: CreationStageInput): boolean {
  return input.demoVersions.length > 0;
}

function hasExport(input: CreationStageInput): boolean {
  return input.exportBundles.length > 0;
}

/**
 * Derive the Creation Chain stage from a workspace snapshot.
 *
 * Progress is monotonic within a single snapshot evaluation: a step is `done`
 * only when its own asset exists, `blocked` when an earlier prerequisite is
 * missing, `active` when it is the next actionable step, and `todo` otherwise.
 */
export function deriveCreationStage(input: CreationStageInput): CreationStage {
  const ideaDone = input.latestIntake !== null;
  const songSpecDone = hasDraftSongSpec(input.versions);
  const approveDone = hasApprovedSongSpec(input.versions);
  const compositionDone = hasComposition(input);
  const arrangementDone = hasArrangement(input);
  const demoDone = hasDemo(input);
  const exportDone = hasExport(input);

  const flags: Record<CreationStepId, boolean> = {
    idea: ideaDone,
    song_spec: songSpecDone,
    approve: approveDone,
    composition: compositionDone,
    arrangement: arrangementDone,
    demo: demoDone,
    export: exportDone,
  };

  // The active step is the first one not yet done.
  let activeIndex = STEP_ORDER.findIndex((step) => !flags[step.id]);
  if (activeIndex === -1) {
    activeIndex = STEP_ORDER.length - 1;
  }

  const steps: CreationStep[] = STEP_ORDER.map((step, index) => {
    if (flags[step.id]) {
      return { id: step.id, status: "done", anchor: step.anchor };
    }
    if (index === activeIndex) {
      return { id: step.id, status: "active", anchor: step.anchor };
    }
    // A later step is blocked until the active one is completed.
    return { id: step.id, status: "blocked", anchor: step.anchor };
  });

  const complete = exportDone;
  return { currentIndex: complete ? -1 : activeIndex, steps, complete };
}
