# ClipForge AI — Subtitle & Karaoke Styling Engine

## 1. Overview

The Subtitle & Karaoke Styling Engine provides broadcast-quality subtitle rendering for local-first short video generation. It transforms word-level Whisper transcription timestamps into styled Advanced SubStation Alpha (`.ass` v4.00+) scripts with viral karaoke word highlighting, bold strokes, drop shadows, and responsive mobile-safe margins.

## 2. Core Architecture

```
Whisper Transcripts (JSON) ──► SubtitleService (Clip Time Conversion)
                                         │
                                         ▼
                            SubtitleSegments + SubtitleWords
                                         │
                                         ▼
                             CaptionPreset (8 Styles)
                                         │
                                         ▼
                             SubtitleRenderer (.ass Script)
                                         │
                                         ▼
                            FFmpeg libass Burn-in Filter
```

### 2.1 Clip-Relative Timestamp Normalization

When extracting subtitles from a parent video transcript for a cut clip:
$$\text{clip\_time} = \max(0, \text{source\_time} - \text{clip.start\_time})$$

Any word ending before $\text{clip.start\_time}$ or starting after $\text{clip.end\_time}$ is strictly filtered out. Word boundary offsets are clamped to $[0, \text{clip.duration\_seconds}]$ preserving chronological order.

### 2.2 ASS Color Conversion

Standard hex colors (`#RRGGBB`) are converted to libass color syntax:
$$\&H[AA][BB][GG][RR]$$
where:
- $AA$: Transparency from `00` (100% opaque) to `FF` (100% transparent).
- $BB$: Blue component hex.
- $GG$: Green component hex.
- $RR$: Red component hex.

Example:
- White `#FFFFFF` $\to$ `&H00FFFFFF`
- Yellow `#FACC15` $\to$ `&H0015CCFA`
- Cyan `#38BDF8` $\to$ `&H00F8BD38`

### 2.3 Windows Filesystem Path Escaping for FFmpeg

When passing Windows file paths to the FFmpeg `ass=filename='...'` video filter:
1. Backslashes (`\`) are converted to forward slashes (`/`).
2. Drive letter colon (`:`) is escaped with a backslash (`\:`).

Example:
`C:\Users\User\AppData\Local\Temp\subs.ass` $\to$ `C\:/Users/User/AppData/Local/Temp/subs.ass`

## 3. Built-In Distinctive Presets

| Preset Name | Font Family | Size | Primary / Highlight | Animation Style | Alignment | MarginV |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bold Creator** | Arial Black | 72 | `#FFFFFF` / `#FACC15` (Yellow) | `karaoke_pop` | Bottom-Center (2) | 280px |
| **Clean Minimal** | Arial | 58 | `#FFFFFF` / `#38BDF8` (Cyan) | `word_by_word` | Bottom-Center (2) | 240px |
| **Podcast Highlight**| Trebuchet MS| 64 | `#F8FAFC` / `#FB923C` (Orange) | `karaoke_pop` | Bottom-Center (2) | 220px |
| **Cinematic** | Georgia | 56 | `#FEF08A` / `#F59E0B` (Amber) | `phrase_fade` | Bottom-Center (2) | 180px |
| **Gaming** | Impact | 74 | `#F0FDF4` / `#22C55E` (Cyber Green)| `karaoke_pop` | Bottom-Center (2) | 300px |
| **Educational** | Segoe UI | 60 | `#F1F5F9` / `#3B82F6` (Royal Blue) | `word_by_word` | Bottom-Center (2) | 240px |
| **Classic Subtitles**| Arial | 50 | `#FFFFFF` / `#FFFFFF` | `static` | Bottom-Center (2) | 160px |
| **High Contrast** | Arial Black | 66 | `#FEF08A` / `#EF4444` (Crimson)| `karaoke_pop` | Bottom-Center (2) | 260px |

## 4. Animation Syntax

### 4.1 Viral Karaoke Pop (`karaoke_pop`)
Active spoken words are scaled up by 10% and colored with the vibrant highlight color:
```
{\c&H0015CCFA&\fscx110\fscy110}HighlightedWord{\r}
```
Words in the rest of the phrase remain in primary color without scaling.

### 4.2 Word-by-Word Reveal (`word_by_word`)
Words appear cumulatively as they are spoken while future words in the chunk are hidden using full transparency `{\c&HFFFFFFFF}`.

### 4.3 Phrase Fade (`phrase_fade`)
Phrases smoothly fade in and out using ASS `\fad(150,150)` tags.

## 5. Safe Margin Standards

To prevent mobile app UI elements (TikTok captions, Reels author tags, YouTube Shorts buttons) from occluding subtitles, bottom-aligned presets maintain a vertical margin of $\ge 220\text{px}$ on a $1080 \times 1920$ canvas. Left and right margins are maintained at $\ge 40\text{px}$.
