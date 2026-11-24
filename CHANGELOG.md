# What's new in Maptro

The newest first. The version shows at the bottom of the Disclaimer. When adding one, change `VERSION` in `index.html` and `sw.js` to match (the tests check all three agree).

## 1.11, 24 Nov 2026: install it, use it offline, use it without colour
- **Add to Home Screen** opens Maptro full screen in true black, with its own icon: the Yellow and Blue lines crossing.
- **Works offline.** Once opened, Maptro opens again with no signal and the trains keep running, from the saved timetable. With a signal it always fetches the newest timetable first. Parts of the map seen before are kept too; anywhere else is black, with the trains still on it.
- **Line codes.** Station cards show each line as a short code on its colour (Y, B, AE…), so lines can be told apart without telling colours apart.
- **Text view.** The chosen lines as a list: trains running on each, and every station's next train in each direction. A screen reader or the Tab key finds it first on the page, and the Disclaimer links to it.
- The Disclaimer shows the version and links here.

## 1.10, 24 Nov 2026: stations where they really are
- 50 stations moved to their OpenStreetMap positions, and the track bent to meet them.
- A weekly check compares every station with OpenStreetMap; the DMRC feed check runs only by hand.

## 1.9, 24 Nov 2026: Sundays and special days
- Sunday first trains start later (06:00; 07:00 on Pink, Magenta and Grey).
- Days DMRC announces its own timings for, like Holi and Diwali, run them.
- A simulation keeps the date, so running past 3 am moves on to the next day's timetable.

## 1.8, 24 Nov 2026: trains pull away and brake
- Trains speed up out of a station and slow into the next, still on the timetable's times.
- Trains wait longer at interchanges (35 s) without changing any other stop's time.

## 1.7, 24 Nov 2026: easier on the battery
- A frame is drawn only when a train would visibly move, and only trains on or near the screen are drawn.

## 1.6, 24 Nov 2026: an honest clock
- The clock reads "Now", not "Live".
- The Disclaimer names the timetable's sources and dates and which day's timetable is running.
- A phone clock more than 2 minutes out is corrected from the server's time.

## 1.5, 24 Nov 2026: DMRC's train frequencies
- Departures follow DMRC's published frequencies (as on 31 Aug 2026), with separate weekday, Saturday and Sunday timetables.
- Branch trains alternate on shared track, and trains turn back where DMRC says they do.

## 1.4, 24 Nov 2026: the zoom update
- Brighter line colours made for true black.
- Everything sizes with zoom; zoomed out, the map shows the network's shape and trains appear as you zoom in.

## 1.3, 24 Nov 2026: trains that bend
- Station dots; trains bend along the track and slide into stations.

## 1.2, 24 Nov 2026: one visual system
- Full-strength lines and glowing bullet trains.

## Before 1.2, 23 and 24 Nov 2026
- The redesign: WebGL trains on an OpenStreetMap basemap in true black, a line picker, train and station cards, and a direction picker. It opens on the Airport Express.
- The timetable: fixes to DMRC's 2023 feed, Phase 4 sections it is missing, Punjabi Bagh West on the Green Line, and running times tuned to Google Maps.
