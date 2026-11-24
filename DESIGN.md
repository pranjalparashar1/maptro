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
6. **Honest.** Positions come from the timetable. The Disclaimer says so once, names the timetable's sources and dates and which day's timetable is running, and each train card says "Scheduled" or "Estimated". Nothing is called live: on a map of moving trains, "Live" reads as GPS tracking, so the real-time clock mode is "Now" (1.6).
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
- State colours are few and small: the green dot beside "Now", amber when the clock runs fast, a white fill when Follow is on.
- The primary action ("Skip to 8 am", "Tap to reload", Follow when on) is white with black text.
- Line colours are DMRC's own hues, pushed to full vividness for true black in 1.4 (`SHOW` in `index.html`): Pink stays light and Magenta deep, and Rapid Metro is a paler sky blue than the Blue Line, so neighbours never read as one line. They are drawn flat: no gradients, glow, outlines or added light.
- **Full-strength colour.** The track is each line's colour at full strength (`TONES.track` = 1), as bright as the very first Maptro; a toned-down track was tried in 1.2 and read as dull. Station dots are a step lighter (`TONES.platform` = 1.2, OKLab lightness, hue kept); interchange dots are `--ink`.
- Trains are `--ink`, one solid colour, with a faint glow around them. They are the brightest thing on the map and the same on every line; the track under a train says which line it is.

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
| Station labels on the map | 11px zoomed out to 13px close in (terminals 1px more) | 500 / 600, `--ink`, no halo |

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

The clock is only a control in simulation. The time now can't be sped up, so at "Now" the clock is plain text. "Skip to 8 am" starts a simulation at 10×; the clock then shows the speed in amber with a small » and cycles 1×, 10×, 60× on tap, and a "Now" pill appears beside it to go back to real time.

The time is the phone's, unless it is more than 2 minutes off the server's (checked once with a small uncached request): then Maptro uses the server's time and the Disclaimer says so.

### Direction pill
Shown under the line picker when exactly one line is chosen. It is a native `<select>` laid invisibly over a pill, so the phone's own picker opens. Options: "Both directions" (the default, and what any new choice of line resets to), "Rithala → Shaheed Sthal" and "Shaheed Sthal → Rithala". The pill reads "Both directions" or "To Rithala". Only trains, and station departures, in the chosen direction are shown; the track stays. Which way each route runs comes from `directions()` in the core block.

### Count note
"19 trains active", with the line's dot: a small pill that drops in under the controls for 2.6 seconds when the page opens, the lines change (once the picker closes) or the direction changes. It replaced the number that sat in the line picker, which read as a static label. Not shown when no train is running (the quiet-hours sheet says that).

### Trains, track and stations
Flat fills, round geometry, no outlines; the trains' faint glow is the one exception. Everything grows with zoom (1.4). The track's width comes from zoom (`TRACK_W` in `index.html`): 1.5px with all of Delhi on screen, 5.6px at zoom 12, 18px at 15 and 28px at the closest. Every other size comes from one unit, `u`, a train's width, which is the track's width / 2.12 (`sizes()`).

| Part | Size |
|---|---|
| Track | `2u + g` (`g = .12u`): exactly two trains, one per direction, in the line's full colour |
| Station | a dot `2u + g` + `max(.9u, 1.8px)` across, a step lighter than its line; white at an interchange |
| Train, zoomed in | a bullet `u` wide and `4.6u` long, solid `--ink`, faint glow |
| Train, zoomed out | a dot `1.7 × max(u, 3.2px)` across, solid `--ink`, faint glow, so it stays visible and tappable on a thin track |

### Zoom: show less as you pull back
The further out, the less there is: a whole-city view is the network's shape, and detail arrives as you zoom in.

- **Trains** hide below zoom 11.2 (`TRAIN_Z`, with 0.1 of give either side) when more than one line is chosen, fading out and back in over 250 ms. Then only the track shows, and a quiet note, "Zoom in or pick a line to see trains", sits where the count note goes (muted text on a small panel; it waits while the count note, the line picker or a card is showing). With one line chosen, its trains always show: one line is never too busy.
- **Stations:** interchanges and terminals always show. Ordinary stations fade in between zoom 10.7 and 11.3 (`MINOR_Z`), or always with one line chosen. A station that isn't shown can't be tapped.
- **Names** come in by importance: terminals from zoom 9.4, interchanges from 10.6, the rest from 11.8 (10.4 with one line chosen). Each fades up over half a zoom level from where it first appears, rather than popping on.

- **Dot or train, never in between.** Trains are dots below zoom 12.8 (`ICON_Z`) and trains above it, with 0.1 of give either side so a pinch resting near it doesn't flicker. Crossing it cross-fades the two in 200 ms: only opacity changes, never the shape. (1.2 blended the shapes by zoom, which left a "rugby ball" in between.)
- **Trains bend with the track.** A zoomed-in train is not a picture turned to face its heading. It is a ribbon laid along the track's own points from its tail to its nose, rebuilt every frame and drawn on the GPU, so through a bend every part of the train follows the curve. The bullet shape is worked out per pixel along and across that ribbon. (A rigid sprite has to pick one angle, so in a bend it cut the corner and swung round late.)
- **Trains merge into stations.** Station dots are drawn over the trains. Arriving, a train's nose stops at the station's centre and its tail closes up behind it, so it slides into the dot; while it waits, its light sits in the dot as a white core (in the line's colour at an interchange), growing as the train goes in and shrinking as it comes out. Leaving is the reverse. Zoomed out, the train dot simply slides under the station dot.
- Trains run on the left side of the track, as Delhi's do. The picked train gets a white outline, `2.5g` out, that pulses.
- Real station footprints were considered and not used: most of Delhi's stations are underground and have no footprint, and the elevated ones are a few pixels across until zoom 15.

### Station names
Plain text in `--ink`, no halo or shadow (it read as a comic), in a light weight (500; 1.3's 600/700 read too bold). Size follows zoom, 11px to 13px. Terminals stand out by weight and size alone (600 and 1px larger), never by colour. Names never overlap each other or another interchange or terminal dot.

### Line picker
A dropdown that unfolds from the pill. Header "Lines" with All and None. One row per line: a ring in the line colour that fills with a tick when chosen, and the line's name. Each row is a real `switch` checkbox stretched over the row, so the tap is native and gives the haptic tick. Tapping outside closes it, and the map then fits the chosen lines.

### Train card
A sheet at the bottom: line colour bar, "Yellow Line", "to Huda City Centre", close. Body: minutes to the next stop and its name (or "At" while dwelling). Footer: "Scheduled" or "Estimated", and Follow. The frame is built once when you tap; only the body text updates (4 times a second, and only when it changes), so a finger on Follow is never under a node that was just rebuilt.

### Station card
Name, a dot for each line, close. Body: the next four departures, each with minutes and destination.

### Quiet hours
When none of the chosen lines has a train running: "The trains are asleep", "Service runs from about 5:30 to 23:30.", and a white "Skip to 8 am".

### Disclaimer
A native `<details>` pill at the bottom left. Open, it says the project is personal and not DMRC's, that positions are scheduled or estimated, where the timetable comes from and how old it is (from `data.json`'s `meta`), which day's timetable is running and that holidays aren't marked, whether the phone's clock is being corrected, and credits OpenStreetMap and OpenFreeMap. It fades out while a card is open.

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
7. **Respect `prefers-reduced-motion`.** Transitions and the pulse beside "Now" are off, the map jumps instead of flying when it refits, and the selected train's ring stops pulsing. Trains still move, because their movement is the information.

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
- Words in use: "Lines", "All", "None", "Now", "Both directions", "To …", "19 trains active", "Zoom in or pick a line to see trains", "Follow", "Next stop", "At", "to …", "Scheduled", "Estimated", "Disclaimer", "The trains are asleep", "Skip to 8 am", "No more trains today.", "Tap to reload".
- Never call a position or the clock live or real-time.

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
- [ ] Map shapes come from the unit `u`; flat fills, no outlines or gradients; glow only on trains; trains are a dot or a train, never between.
- [ ] System font only.
- [ ] No new text that could be cut.
- [ ] DOM motion is transform/opacity only, on an existing curve; no blur or shadow on panels.
- [ ] Works with reduced motion.
- [ ] 44px touch targets; native controls where the phone has one; haptic switch on new buttons.
- [ ] `node --test tests/*.test.mjs` passes.
- [ ] Looked at on a real phone.
