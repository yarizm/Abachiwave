import type { ChordMeasure, MidiNoteEvent } from "@/lib/composition";

/**
 * Schedules one section's chords and melody together so the section view can be
 * heard, not just read.
 *
 * Chords and melody arrive with different beat origins, and reconciling them is
 * the entire point of this module. `ChordEvent.beat` is 1-based within its
 * measure and `ChordMeasure.measure_number` is 1-based within the section —
 * chord-playback.ts already reduces that to a section-local beat offset (minus
 * the cross-section `measureOffset` that file needs and this one does not, since
 * here there is always exactly one section). `MidiNoteEvent.start_beat`, by
 * contrast, is absolute from the start of the whole song. The only place that
 * already turns it into a section-local position is `SectionMelodyStrip`, which
 * subtracts a caller-supplied `startBeat` — in practice `row.notes[0].start_beat`,
 * the section's earliest note — rather than anything it derives itself.
 *
 * `noteStartBeat` is therefore a required parameter here too, not something this
 * module recomputes from `notes[0]`. If it picked its own anchor, it would only
 * agree with the strip by coincidence, and the two would drift apart the moment a
 * caller filtered or reordered notes before handing them to one but not the
 * other. Taking the exact same value both places is what keeps a chord you can
 * see under a note on screen landing on the same beat you hear it.
 */

export type SectionPlaybackInput = {
  measures: ChordMeasure[];
  notes: MidiNoteEvent[];
  /** beat the melody is normalized against — the same value the strip is given */
  noteStartBeat: number;
  beatsPerMeasure: number;
  tempoBpm: number;
  timeSignature: string;
};

export type ScheduledTone = {
  kind: "chord" | "melody";
  /** seconds from the start of the section */
  at: number;
  durationSeconds: number;
  midi: number[];
  velocity: number;
  /** ChordEvent.event_id for chords, MidiNoteEvent.note_id for melody */
  sourceId: string;
};

export type SectionSchedule = {
  tones: ScheduledTone[];
  beatSeconds: number;
  /** section length in seconds — max of the chord grid and the melody tail */
  totalSeconds: number;
  totalBeats: number;
};

/**
 * Pure. No Tone import here on purpose: this is the function the unit tests
 * exercise directly, so the alignment arithmetic can be checked without a Web
 * Audio context. `startSectionPlayback` below is the only thing that touches Tone.
 */
export function buildSectionSchedule(input: SectionPlaybackInput): SectionSchedule {
  const beatsPerMeasure = sanitizeBeatsPerMeasure(input.beatsPerMeasure);
  const tempoBpm = sanitizeTempoBpm(input.tempoBpm);
  const [, denominator] = parseTimeSignature(input.timeSignature);
  const beatSeconds = (60 / tempoBpm) * (4 / denominator);

  const tones: ScheduledTone[] = [];

  for (const measure of input.measures) {
    for (const event of measure.events) {
      // No resolved pitches means nothing to trigger. chord-playback.ts skips
      // these the same way rather than sounding an empty voicing.
      if (event.midi_notes.length === 0) continue;
      const sectionBeat = (measure.measure_number - 1) * beatsPerMeasure + (event.beat - 1);
      tones.push({
        kind: "chord",
        at: sectionBeat * beatSeconds,
        durationSeconds: Math.max(0.08, event.duration_beats * beatSeconds * 0.92),
        midi: [...event.midi_notes],
        velocity: 0.72,
        sourceId: event.event_id,
      });
    }
  }

  // Track the melody's tail as we go rather than in a second pass: it can run
  // past the chord grid (a held final note) or stop well short of it (a pickup
  // section with bars of silence at the end), and totalBeats below needs it.
  let melodyTailBeats = 0;
  for (const note of input.notes) {
    const sectionBeat = note.start_beat - input.noteStartBeat;
    melodyTailBeats = Math.max(melodyTailBeats, sectionBeat + note.duration_beats);
    tones.push({
      kind: "melody",
      at: sectionBeat * beatSeconds,
      // Chords get a shortened, gapped duration because a chord's duration_beats
      // runs up to the next chord change and would otherwise smear into it.
      // A melody note's duration is already the intended phrasing, so it keeps
      // it in full.
      durationSeconds: Math.max(0.05, note.duration_beats * beatSeconds),
      midi: [note.pitch],
      // Velocity 0 is valid MIDI (and shows up in transcribed data) but should
      // not be literally inaudible on a surface meant for judging the melody.
      velocity: Math.max(0.15, note.velocity / 127),
      sourceId: note.note_id,
    });
  }

  // A stable sort keeps same-instant ties in push order (chords first, above),
  // and the explicit kind tiebreak makes "chords before melody" a guarantee
  // rather than an accident of insertion order.
  tones.sort(
    (left, right) =>
      left.at - right.at || (left.kind === right.kind ? 0 : left.kind === "chord" ? -1 : 1),
  );

  const chordGridBeats = input.measures.length * beatsPerMeasure;
  // Floored at one bar so an empty section still has a playable length instead
  // of collapsing the transport loop to zero seconds.
  const totalBeats = Math.max(beatsPerMeasure, chordGridBeats, melodyTailBeats);

  return {
    tones,
    beatSeconds,
    totalSeconds: totalBeats * beatSeconds,
    totalBeats,
  };
}

export type SectionPlaybackOptions = SectionPlaybackInput & {
  loop: boolean;
  metronome: boolean;
  /** fires on each sounded chord/note so the UI can highlight it; null when idle */
  onSound: (tone: ScheduledTone | null) => void;
  /** playhead position in section-local beats, for drawing a cursor */
  onProgress: (beat: number) => void;
  onEnded: () => void;
};

export type SectionPlaybackHandle = {
  stop: () => void;
};

export async function startSectionPlayback(
  options: SectionPlaybackOptions,
): Promise<SectionPlaybackHandle> {
  const Tone = await import("tone");
  await Tone.start();

  const schedule = buildSectionSchedule(options);
  const beatsPerMeasure = sanitizeBeatsPerMeasure(options.beatsPerMeasure);

  const transport = Tone.getTransport();
  transport.stop();
  transport.cancel();
  transport.seconds = 0;
  transport.bpm.value = sanitizeTempoBpm(options.tempoBpm);
  transport.loop = options.loop;
  transport.loopStart = 0;
  transport.loopEnd = schedule.totalSeconds;

  const chordSynth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "triangle8" },
    envelope: { attack: 0.02, decay: 0.15, sustain: 0.36, release: 0.8 },
    volume: -11,
  }).toDestination();
  // Melody is the part being judged here, not the accompaniment, so it gets a
  // brighter oscillator and more headroom to sit above the chord bed rather than
  // blend into it.
  const melodySynth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "sawtooth" },
    envelope: { attack: 0.01, decay: 0.1, sustain: 0.5, release: 0.4 },
    volume: -6,
  }).toDestination();
  const click = new Tone.MembraneSynth({
    pitchDecay: 0.008,
    octaves: 2,
    envelope: { attack: 0.001, decay: 0.05, sustain: 0, release: 0.03 },
    volume: -17,
  }).toDestination();

  for (const tone of schedule.tones) {
    const synth = tone.kind === "chord" ? chordSynth : melodySynth;
    const frequencies = tone.midi.map((midiNote) => Tone.Frequency(midiNote, "midi").toFrequency());
    transport.schedule((time) => {
      options.onSound(tone);
      synth.triggerAttackRelease(frequencies, tone.durationSeconds, time, tone.velocity);
    }, tone.at);
  }

  if (options.metronome) {
    for (let beatIndex = 0; beatIndex < schedule.totalBeats; beatIndex += 1) {
      transport.schedule((time) => {
        const accent = beatIndex % beatsPerMeasure === 0;
        click.triggerAttackRelease(accent ? "C3" : "C2", "32n", time, accent ? 0.75 : 0.35);
      }, beatIndex * schedule.beatSeconds);
    }
  }

  let stopped = false;
  let frame: number | null = null;

  // requestAnimationFrame does not exist under the Node test runner. Guarding it
  // here, rather than at module scope, is what keeps this file importable there
  // while still driving the playhead correctly in the browser.
  if (typeof requestAnimationFrame !== "undefined") {
    const tick = () => {
      if (stopped) return;
      options.onProgress(transport.seconds / schedule.beatSeconds);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
  }

  if (!options.loop) {
    transport.scheduleOnce(() => {
      if (stopped) return;
      options.onSound(null);
      options.onEnded();
    }, schedule.totalSeconds);
  }
  transport.start("+0.05", 0);

  return {
    stop() {
      if (stopped) return;
      stopped = true;
      transport.stop();
      transport.cancel();
      transport.seconds = 0;
      chordSynth.dispose();
      melodySynth.dispose();
      click.dispose();
      if (frame !== null && typeof cancelAnimationFrame !== "undefined") {
        cancelAnimationFrame(frame);
      }
      options.onSound(null);
    },
  };
}

function sanitizeTempoBpm(value: number): number {
  return Number.isFinite(value) && value > 0 ? value : 120;
}

function sanitizeBeatsPerMeasure(value: number): number {
  return Number.isFinite(value) && value > 0 ? value : 4;
}

/** Same shape as chord-playback.ts's parser: a malformed signature must not throw. */
function parseTimeSignature(value: string): [number, number] {
  const [rawNumerator, rawDenominator] = value.split("/");
  const numerator = Number(rawNumerator) || 4;
  const denominator = Number(rawDenominator) || 4;
  return [Math.max(1, numerator), Math.max(1, denominator)];
}
