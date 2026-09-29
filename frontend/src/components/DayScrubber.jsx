import { motion } from "motion/react";
import { useEffect, useState } from "react";

const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** Day picker with a play button that steps through the forecast days. */
function DayScrubber({ dates, value, onChange }) {
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing || !dates.length) return;
    const id = setInterval(() => onChange((d) => (d + 1) % dates.length), 1200);
    return () => clearInterval(id);
  }, [playing, dates.length, onChange]);

  return (
    <div className="scrubber" role="group" aria-label="Forecast day">
      <button type="button" className="scrubber__play" onClick={() => setPlaying((p) => !p)} aria-pressed={playing}
        aria-label={playing ? "Pause animation" : "Play through the days"}>
        <span className="material-symbols-outlined" aria-hidden="true">{playing ? "pause" : "play_arrow"}</span>
      </button>
      <div className="scrubber__days">
        {dates.map((d, i) => {
          const date = new Date(d + "T00:00:00Z");
          const label = i === 0 ? "Today" : i === 1 ? "Tomorrow" : WEEKDAY[date.getUTCDay()];
          return (
            <button type="button" key={d} className={"scrubber__day" + (i === value ? " is-active" : "")}
              onClick={() => (setPlaying(false), onChange(i))} aria-pressed={i === value}>
              {i === value && <motion.span layoutId="scrubber-pill" className="scrubber__pill" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
              <span className="scrubber__label">{label}</span>
              <span className="scrubber__date">{date.getUTCDate()}/{date.getUTCMonth() + 1}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default DayScrubber;
