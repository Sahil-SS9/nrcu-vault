# Local private studio

This branch is a local-only personal video-production workspace. It must not be pushed or published.

## Commands

```bash
# Validate a project
python3 -m pipeline.cli validate \
  --manifest productions/teknium-portal-sequence/v2/studio.toml \
  --repo-root .

# Create a safe selective-shot run
python3 -m pipeline.cli plan \
  --manifest productions/teknium-portal-sequence/v2/studio.toml \
  --repo-root . --run-id draft-001 --shots 04-visor-flash,07-portal-open

# Resume and render only missing H3 shots
python3 -m pipeline.cli render \
  --manifest productions/teknium-portal-sequence/v2/studio.toml \
  --repo-root . --run-id draft-001 --resume --skip-existing

# Export a local Suno-ready package; this does not call Suno
python3 -m pipeline.cli suno-export \
  --destination outputs/example/suno-package.json \
  --title "Private cue" --style "Cinematic electronic" \
  --lyrics-file path/to/lyrics.txt --source-project example

# Import a manually downloaded local audio file
python3 -m pipeline.cli suno-import \
  --source path/to/take.wav --destination outputs/example/audio/take.wav

# Create a vertical delivery master
python3 -m pipeline.cli deliver \
  --source path/to/master.mp4 --destination outputs/example/final-9x16.mp4 \
  --profile 9x16

# Verify the pinned H3 runtime
python3 -m pipeline.runtime_preflight --lock runtime/h3.lock.json

# Cold-start smoke on an alternate local port without sharing live temp/DB state
H3_PORT=8190 \
H3_TEMP=/tmp/nrcu-h3-launch-proof \
H3_DATABASE_URL=sqlite:///:memory: \
./runtime/start-h3-local.sh

# Enter the offline/private FastVideo environment after model download
source runtime/fastvideo-private-env.sh
```

## Privacy contract

- Video endpoints must resolve to localhost.
- New keyframes must use local ComfyUI or pre-approved local files; remote image generation is rejected by the project contract.
- Project manifests must declare `privacy = "local-private"`.
- Inputs must be physically contained under the trusted project root.
- Suno is prompt-export/audio-import only; cloud generation is never called.
- Run outputs are written under ignored `outputs/` directories and never overwrite an approved file.
- FastVideo is isolated under `/home/kensei/video-runtimes/FastVideo`.
- No publishing, upload, social or public Git operation is part of this workflow.
