# Maptro design system

How Maptro looks, moves and behaves, taken from `index.html`. Where this file and the code disagree, the code wins. Change this file in the same PR as any change to the look.

Maptro is a phone-first map of Delhi Metro trains running to the timetable. Everything below serves one aim: let someone open it on a phone, see the trains moving, and tap one, with as little in the way as possible.

The principles were drawn from how Kiron (pranjal's quiz app) was built: its design system and its product record. The colours are Maptro's own.

---

## 1. Principles (apply these first)

1. **The map is the app.** Full screen, edge to edge. Controls float over it and stay small: two pills at the top, one sheet at the bottom when something is tapped.
2. **Native first.** Use what the phone already does before building anything: a real `<details>` for the Disclaimer, real checkboxes with the `switch` attribute for the line list, the system haptic tick, system font, the system's focus ring and reduced-motion setting.
3. **Ruthlessly minimal text.** No intro copy, no headings, no labels that repeat what a control shows. The line picker shows coloured dots and a short name. A train card is the line, where it is going, the next stop and when.
4. **Phone only.** Design for an iPhone held in one hand. Laptops only have to work. Every touch target is at least 44px, even where the drawn shape is smaller.
5. **Plain, kind copy.** Sentence case. "The trains are asleep", not "No service". "Couldn't load the timetable" with a "Tap to reload" button, never a bare error.
6. **Honest.** Positions come from the timetable. The Disclaimer says so once, and each train card says "Scheduled" or "Estimated". Nothing is called live except the clock mode, which means "real time now".
7. **Smooth beats rich.** The DOM interface animates only transform and opacity. If an effect cannot run on the GPU, it does not ship.

---

## 2. Colour tokens

Always dark, and **true black** (`#000`), so an OLED phone switches those pixels off and the line colours stand out against nothing. No light mode. `color-scheme: dark`; `theme-color` is `#000000`.

```css
:root {
  /* layers: true black page, then greys stepping up */
  --bg: #000; --surface: #0d0d0d; --surface2: #1c1c1c; --line: #2a2a2a;
  --ink: #f4f4f4; --muted: #8f8f8f; --faint: #5e5e5e;
  /* state */
  --live: #3ddc84; --sim: #f5c400; --focus: rgba(255,255,255,.7);
  /* "do this" is white: an inverted pill */
  --act: #f4f4f4; --act-ink: #000;
}
```

Rules:
- **Colour belongs to the metro lines.** The interface itself is black, greys and white. That way the only colour on screen means a line, and nothing in the chrome competes with it.
- Resting layers step up from black: page `--bg`, panels `--surface` with a 1px `--line` hairline, buttons and pressed rows `--surface2`.
- State colours are few and small: the green dot beside "Live", amber when the clock runs fast, a white fill when Follow is on.
- The primary action ("Skip to 8 am", "Tap to reload", Follow when on) is white with black text.
- Line colours are DMRC's own, nudged brighter where they read too dark on black (`SHOW` in `index.html`). They are drawn flat: no gradients, glow, outlines or added light.
- **One light, three tones.** Each line's colour comes in three tones, made by scaling its OKLab lightness so the hue holds (a darker yellow stays yellow, not olive): the track at rest is 80% (`TONES.track`), a platform is the full colour, and the trains are `--ink`. Brighter means "something is here". Trains are the brightest thing on the map and the same white on every line; the track under a train says which line it is.
- The leading coach of each train is `--ink`; the others are `--ink` at 74%. That is the only direction cue.

### Basemap
OpenStreetMap data, served as vector tiles by OpenFreeMap (free, no key, made to be linked from other sites), drawn in Maptro's own style (`BLACK_STYLE` in `index.html`):

| Layer | Colour | Notes |
|---|---|---|
| Background | `#000` | |
| Parks, woods | `#06100a`, `#050c07` | barely green; you notice the Ridge, not a fill |
| Water | `#08131f` | the Yamuna reads as a dark blue band |
| Buildings (z14+) | `#0c0c0c` | |
| Minor roads (z12+) | `#121212` | |
| Major roads | `#1d1d1d` | |

No place labels, fonts or icons load from the basemap. Station names are Maptro's own, drawn on top and decluttered. If the tiles cannot load, the map is simply black and the trains still run.

---

## 3. Type

The system font (`-apple-system`, SF Pro on iPhone). No web font loads: it is native, instant and matches the rest of the phone.

| Use | Size | Weight |
|---|---|---|
| Body, pills | 15px / 1.4 | 600 in pills |
| Card title | 17px / 1.25 | 700 |
| Minutes to next stop | 22px | 700, tabular numerals |
| Card subtitle, departures | 14px | 400-500 |
| Small notes ("Scheduled", Disclaimer) | 13px | 600 |
| Station labels on the map | 12px (13px terminals) | 600 / 700, black halo |

Numbers that change (the clock, train count, minutes) use tabular numerals so they don't jitter.

---

## 4. Spacing, radii, layout

- Safe areas: everything is placed with `env(safe-area-inset-*)`. A black strip covers the status bar so the map never runs under the phone's clock.
- Heights use `100svh` (not `vh`), so Safari's sliding toolbar never resizes the page.
- Panels sit 12px from the screen edges. Sheets are at most 420px wide.
- Radii: pills 22px (`--r-pill`), sheets 24px (`--r-sheet`), rows 14px (`--r-row`).
- Touch targets: 44px (`--tap`) minimum. The card's close button draws a 32px circle inside a 44px target.
- No visible scrollbars. No rubber-band bounce (`overscroll-behavior: none`).

---

## 5. Components

### Top pills
Left: the line picker (coloured dots, a short name such as "Airport Express" or "3 lines", a chevron). Right: the clock (time and a state word). It opens on the Airport Express line.

The clock is only a control in simulation. Live time can't be sped up, so in Live the clock is plain text. "Skip to 8 am" starts a simulation at 10×; the clock then shows the speed in amber with a small » and cycles 1×, 10×, 60× on tap, and a "Live" pill appears beside it to go back to real time.

### Direction pill
Shown under the line picker when exactly one line is chosen. It is a native `<select>` laid invisibly over a pill, so the phone's own picker opens. Options: "Both directions" (the default, and what any new choice of line resets to), "Rithala → Shaheed Sthal" and "Shaheed Sthal → Rithala". The pill reads "Both directions" or "To Rithala". Only trains, and station departures, in the chosen direction are shown; the track stays. Which way each route runs comes from `directions()` in the core block.

### Count note
"19 trains active", with the line's dot: a small pill that drops in under the controls for 2.6 seconds when the page opens, the lines change (once the picker closes) or the direction changes. It replaced the number that sat in the line picker, which read as a static label. Not shown when no train is running (the quiet-hours sheet says that).

### Trains, track and stations: one system
The first draft of 1.2 showed that the map, the track and the trains read as three design languages: the basemap was flat filled shapes, the track was outlined rails, the trains were a white sprite with a sharp nose and a rim. Everything is now built from the basemap's own language: **flat fills, rounded geometry, no outlines, one unit.**

**The unit.** `u` is a train's width (`sizes()` in `index.html`): 3px zoomed out, growing to 8px. Everything else is a multiple of it.

| Part | Size | Corner radius |
|---|---|---|
| Train | `u` wide, `4.6u` long, three coaches with gaps of `g = .12u` | `.3u` |
| Track | `2u + g`: exactly two trains, one per direction, with `g` between | round joins, like the roads |
| Platform | track width plus `.45u` all round; zoomed out a round mark, from about zoom 11.5 it stretches to hold a train | concentric with a train's: `.3u + .45u` |
| Roads | MapLibre lines with round caps and joins | |

- **Track:** one flat band in the line's track tone, two trains wide. Trains run on the left side, as Delhi's do, so the two directions never overlap. A train fills its half of the band edge to edge.
- **Trains:** three flat coaches with round corners, the leading one lit. No windscreen, headlight, glow, rim or trail. The heading is averaged over 90 m of track, so trains turn smoothly through bends. The picked train gets a white outline, `2.5g` out, that pulses.
- **Stations are drawn as their platforms:** the track widening, in the line's full colour, a train long, so a train visibly pulls in and stops inside it. Each line gets its own platform where it stops, so an interchange shows each line's platform where it really is; interchanges are told apart by their bolder label.
  - Real station footprints were considered and not used: most of Delhi's stations are underground and have no footprint, the elevated ones are a few pixels across until zoom 15, and OpenStreetMap outlines vary in quality. The platform says the same thing (a train stops here, along this track) at every zoom.
- **Basemap:** unchanged colours; roads now have round caps and joins, the same geometry as the track.

### Line picker
A dropdown that unfolds from the pill. Header "Lines" with All and None. One row per line: a ring in the line colour that fills with a tick when chosen, and the line's name. Each row is a real `switch` checkbox stretched over the row, so the tap is native and gives the haptic tick. Tapping outside closes it, and the map then fits the chosen lines.

### Train card
A sheet at the bottom: line colour bar, "Yellow Line", "to Huda City Centre", close. Body: minutes to the next stop and its name (or "At" while dwelling). Footer: "Scheduled" or "Estimated", and Follow. The frame is built once when you tap; only the body text updates (4 times a second, and only when it changes), so a finger on Follow is never under a node that was just rebuilt.

### Station card
Name, a dot for each line, close. Body: the next four departures, each with minutes and destination.

### Quiet hours
When none of the chosen lines has a train running: "The trains are asleep", "Service runs from about 5:30 to 23:30.", and a white "Skip to 8 am".

### Disclaimer
A native `<details>` pill at the bottom left. Open, it says the project is personal and not DMRC's, that positions are scheduled or estimated, and credits OpenStreetMap and OpenFreeMap. It fades out while a card is open.

### Buttons
`.btn`: 44px, pill, `--surface2`. `.btn.act` / `.btn.on`: white fill, black text. All buttons use `.press`.

---

## 6. Motion rules

1. **The DOM interface animates `transform` and `opacity` only.** Never width, height, colour, background, shadow or filters. A tick filling a ring is a coloured layer fading and scaling in, not a background transition.
2. **No blur, no shadows on panels.** They sit over a WebGL map that redraws every frame, so a `backdrop-filter` would be recomputed every frame. Panels are solid near-black instead, which on a black map looks the same.
3. **The DOM interface uses CSS transitions only.** No JavaScript animation of the interface.
4. **The map is the exception, on purpose.** Trains move every frame in a `requestAnimationFrame` loop that draws to WebGL (120 Hz on ProMotion phones). That loop only uploads buffers and draws; it never touches the DOM layout. The card text is the one DOM write it makes, 4 times a second, and only when the text changed.
5. **One motion, one curve.** Reuse the curves below rather than inventing one for an element.
6. **Never retime existing motion, and never go faster.** Changes ship one at a time and are judged by feel on a phone.
7. **Respect `prefers-reduced-motion`.** Transitions and the Live pulse are off, the map jumps instead of flying when it refits, and the selected train's ring stops pulsing. Trains still move, because their movement is the information.

| Token | Value | Used for |
|---|---|---|
| `--fold` | 520ms `cubic-bezier(.32,.72,0,1)` | line picker opening, chevrons |
| `--settle` | `cubic-bezier(.25,.6,.3,1)`, 240-420ms | sheets in and out, fades, picker closing |
| `--spring` | 340ms `cubic-bezier(.3,1.6,.5,1)` | a pressed control springing back, ticks popping in |
| Map refit | 900ms (MapLibre's default ease) | fitting the chosen lines |
| Count note | in on `--spring` 340ms, out on `--settle` 420ms | "19 trains active" |

---

## 7. Interaction rules

- **Tap to learn, drag to look.** Tap a train or station for its card; tap empty map to close it. Pinch and drag move the map; rotating and tilting are off.
- **Press feedback on everything tappable**, instant on press (`scale(.95)`, no transition, because the finger may be about to drag) and springing back on release.
- **Haptics:** an invisible real `<input type="checkbox" switch>` is stretched over each button (opacity 0, never `appearance: none`), so iOS gives its own tick; the tap is passed on to the button. Android gets `navigator.vibrate(8)` instead. Tapping a station also vibrates on Android. iOS can't tick for taps on the map canvas.
- **No modals.** The picker is a dropdown, cards are sheets, nothing blocks the map.
- **Remembered:** the chosen lines (localStorage `maptro-lines-v2`; v2 so everyone sees the new Airport Express default once). The direction is not remembered: a line always opens with both.
- **Keyboard (laptops):** every control is a real button or checkbox, with a 3px white focus ring.

---

## 8. Copy

- Short, plain, warm. Sentence case, no all-caps labels. One line wherever possible.
- Words in use: "Lines", "All", "None", "Live", "Both directions", "To …", "19 trains active", "Follow", "Next stop", "At", "to …", "Scheduled", "Estimated", "Disclaimer", "The trains are asleep", "Skip to 8 am", "No more trains today.", "Tap to reload".
- Never call a position live or real-time.

---

## 9. Judgement calls

Where a Kiron rule didn't carry over as-is, and why:

- **No `requestAnimationFrame`** → kept for the WebGL train loop only. Trains moving smoothly is the product, and WebGL draws on the GPU without touching layout, which is the point of the rule. The DOM interface follows the rule.
- **No numbers on screen** → Kiron hides counts because a quiz's numbers feel like a test. On a map, the time, the minutes to the next stop and the train count are the information. The per-line counts in the picker were cut, though: the total in the pill is enough.
- **Poppins** → the system font instead. Native first wins over brand, and it means no font download.
- **Orange and blue accents** → not copied. Colour on Maptro belongs to the metro lines, so the chrome is greyscale and the action colour is white.
- **Glass and blur** (Maptro's earlier look) → removed. It cost a blur every frame over a moving map, and on true black a solid panel reads the same.
- **The train count moved out of the line picker** into the count note. A number that never stops changing beside a label read as part of the label; shown for a moment after a change, it answers "how many?" exactly when it is asked.
- **The train card no longer shows the trip's start time.** It was a long uppercase line that few would read; the train's place on the map already identifies it.

---

## 10. How changes are made

From Kiron's record, and they apply here too:

- **Judge on the phone, not in screenshots.** Screenshots from a desktop browser show colours darker and punchier than an iPhone does. Open the live page on a phone before calling a look done.
- **One change at a time.** Kiron 1.4 shipped nine changes at once, felt laggy, and was rolled back; the same nine, one per release, were fine. When something feels off, it should be obvious which change did it.
- **Smoother, faster, lighter, without losing function or form** is the bar for a clean-up.
- **Test with real people.** Watching someone use it shows confusion that tests never will.

## 11. Checklist for any change

- [ ] Uses the tokens above; colour only for lines and state.
- [ ] Map shapes come from the unit `u` and its radii; flat fills, no outlines, glow or gradients.
- [ ] System font only.
- [ ] No new text that could be cut.
- [ ] DOM motion is transform/opacity only, on an existing curve; no blur or shadow on panels.
- [ ] Works with reduced motion.
- [ ] 44px touch targets; native controls where the phone has one; haptic switch on new buttons.
- [ ] `node --test tests/*.test.mjs` passes.
- [ ] Looked at on a real phone.
