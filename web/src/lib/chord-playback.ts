import type { ChordSection } from "@/lib/composition";

export type ChordPlaybackOptions = {
  sections: ChordSection[];
  tempoBpm: number;
  timeSignature: string;
  loop: boolean;
  metronome: boolean;
  onEvent: (eventId: string | null) => void;
  onEnded: () => void;
};

export type ChordPlaybackHandle = {
  stop: () => void;
};

export async function startChordPlayback(
  options: ChordPlaybackOptions,
): Promise<ChordPlaybackHandle> {
  const Tone = await import("tone");
  await Tone.start();

  const [beatsPerMeasure, denominator] = parseTimeSignature(options.timeSignature);
  const beatSeconds = (60 / options.tempoBpm) * (4 / denominator);
  const totalMeasures = options.sections.reduce(
    (total, section) => total + section.measures.length,
    0,
  );
  const totalSeconds = Math.max(beatSeconds, totalMeasures * beatsPerMeasure * beatSeconds);
  const transport = Tone.getTransport();
  transport.stop();
  transport.cancel();
  transport.seconds = 0;
  transport.bpm.value = options.tempoBpm;
  transport.loop = options.loop;
  transport.loopStart = 0;
  transport.loopEnd = totalSeconds;

  const synth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "triangle8" },
    envelope: { attack: 0.02, decay: 0.15, sustain: 0.36, release: 0.8 },
    volume: -11,
  }).toDestination();
  const click = new Tone.MembraneSynth({
    pitchDecay: 0.008,
    octaves: 2,
    envelope: { attack: 0.001, decay: 0.05, sustain: 0, release: 0.03 },
    volume: -17,
  }).toDestination();

  let measureOffset = 0;
  for (const section of options.sections) {
    for (const measure of section.measures) {
      const measureStart = (measureOffset + measure.measure_number - 1) * beatsPerMeasure;
      for (const event of measure.events) {
        if (event.midi_notes.length === 0) continue;
        const startSeconds = (measureStart + event.beat - 1) * beatSeconds;
        const durationSeconds = Math.max(0.08, event.duration_beats * beatSeconds * 0.92);
        const frequencies = event.midi_notes.map((note) =>
          Tone.Frequency(note, "midi").toFrequency(),
        );
        transport.schedule((time) => {
          options.onEvent(event.event_id);
          synth.triggerAttackRelease(frequencies, durationSeconds, time, 0.72);
        }, startSeconds);
      }
    }
    measureOffset += section.measures.length;
  }

  if (options.metronome) {
    for (let beatIndex = 0; beatIndex < totalMeasures * beatsPerMeasure; beatIndex += 1) {
      transport.schedule((time) => {
        const accent = beatIndex % beatsPerMeasure === 0;
        click.triggerAttackRelease(accent ? "C3" : "C2", "32n", time, accent ? 0.75 : 0.35);
      }, beatIndex * beatSeconds);
    }
  }

  let stopped = false;
  if (!options.loop) {
    transport.scheduleOnce(() => {
      if (stopped) return;
      options.onEvent(null);
      options.onEnded();
    }, totalSeconds);
  }
  transport.start("+0.05", 0);

  return {
    stop() {
      if (stopped) return;
      stopped = true;
      transport.stop();
      transport.cancel();
      transport.seconds = 0;
      synth.dispose();
      click.dispose();
      options.onEvent(null);
    },
  };
}

function parseTimeSignature(value: string): [number, number] {
  const [rawNumerator, rawDenominator] = value.split("/");
  const numerator = Number(rawNumerator) || 4;
  const denominator = Number(rawDenominator) || 4;
  return [Math.max(1, numerator), Math.max(1, denominator)];
}
