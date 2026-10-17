import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ffmpeg = (await import('ffmpeg-static')).default;

const cues = [
  {
    timeMs: 1000,
    text: "Welcome to the Asset Intelligence Copilot. We built this copilot for operational intelligence across 600 oil wells and over 140,000 real sensor and inspection records.",
  },
  {
    timeMs: 23000,
    text: "Stage one: Ingestion. All structured fleet records are loaded into an embedded SQLite database, while manuals, SOPs, and operator shift notes are indexed for text retrieval.",
  },
  {
    timeMs: 45000,
    text: "Stage two: Deterministic calculations. Mathematical metrics like downtime, spill deadlines, and repair costs run in pure Python, never by an LLM.",
  },
  {
    timeMs: 67000,
    text: "Stage three: Memory isolation. Field corrections are audited and stored in shared memory, while operator conversation histories remain private and isolated.",
  },
  {
    timeMs: 89000,
    text: "Stage four: Citation assembly. Every returned response provides direct citations back to the raw source files and operating manuals.",
  },
  {
    timeMs: 111000,
    text: "Transitioning to the live application. We switch to maintenance lead Robert Hayes. The user picker dynamically loads all 27 fleet operators directly from the final test dataset.",
  },
  {
    timeMs: 126000,
    text: "Robert requests the current production status for WELL-0332. The copilot renders a real-time status card showing a temperature delta of 0.5 degrees Celsius against a 15-degree threshold, confirming the well is shut in.",
  },
  {
    timeMs: 151000,
    text: "Expanding citations surfaces the drone inspection record from January 14th, 2027, along with section 9.3 of the T200 well manual.",
  },
  {
    timeMs: 171000,
    text: "Next, Robert asks: Which wells in Southwest Block 23 are not producing oil right now? Show a table.",
  },
  {
    timeMs: 191000,
    text: "The copilot evaluates all wells in the block, returning seven non-producing wells with complete citations to their recent inspection logs and operating rules.",
  },
  {
    timeMs: 216000,
    text: "Now reviewing the committed evaluation triage. Questions one and two on reservoir pressure and oil production rates cannot be answered because those fields do not exist in the raw schema. Our copilot transparently reports this data gap.",
  },
  {
    timeMs: 251000,
    text: "For questions seven through eleven, the system evaluates gas leak response deadlines, temporary flowline bypasses, and regulator spill compliance with strict deterministic audit trails.",
  },
  {
    timeMs: 286000,
    text: "In summary, Asset Intelligence Copilot delivers auditable, transparent operations intelligence with zero hallucinations. Thank you.",
  },
];

async function main() {
  const tmpDir = path.join(ROOT, 'dist', 'audio_cues');
  fs.mkdirSync(tmpDir, { recursive: true });

  const inputArgs = [];
  const filterParts = [];
  const mixInputs = [];

  console.log('Generating voiceover clips with Windows Speech Synthesizer...');
  const psScript = path.join(ROOT, 'scripts', 'synth_speech.ps1');

  for (let i = 0; i < cues.length; i++) {
    const cue = cues[i];
    const wavPath = path.join(tmpDir, `cue_${i}.wav`);
    console.log(`[${i + 1}/${cues.length}] At ${(cue.timeMs / 1000).toFixed(1)}s: "${cue.text.slice(0, 40)}..."`);
    execFileSync('powershell.exe', [
      '-ExecutionPolicy', 'Bypass',
      '-File', psScript,
      '-Text', cue.text,
      '-OutFile', wavPath,
    ]);

    // Add input for ffmpeg
    inputArgs.push('-i', wavPath);
    // adelay filter expects delay in ms for each channel (left|right)
    filterParts.push(`[${i + 1}:a]adelay=${cue.timeMs}|${cue.timeMs},volume=1.8[a${i}]`);
    mixInputs.push(`[a${i}]`);
  }

  const videoIn = path.join(ROOT, 'docs', 'demo_5min_silent.webm');
  const videoOut = path.join(ROOT, 'docs', 'demo_5min_narrated.webm');

  // Input 0 is the video file
  const filterComplex = `${filterParts.join('; ')}; ${mixInputs.join('')}amix=inputs=${cues.length}:dropout_transition=0:normalize=0[audio]`;

  console.log('Merging audio with video using ffmpeg...');
  const ffmpegArgs = [
    '-y',
    '-i', videoIn,
    ...inputArgs,
    '-filter_complex', filterComplex,
    '-map', '0:v',
    '-map', '[audio]',
    '-c:v', 'copy',
    '-c:a', 'libopus',
    '-b:a', '128k',
    '-shortest',
    videoOut,
  ];

  execFileSync(ffmpeg, ffmpegArgs, { stdio: 'inherit' });

  const stat = fs.statSync(videoOut);
  console.log(`Success! Narrated demo video generated: docs/demo_5min_narrated.webm (${(stat.size / 1024 / 1024).toFixed(2)} MB)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
