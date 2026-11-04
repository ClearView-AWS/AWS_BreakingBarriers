// List / Map for the results on screen. Ported from Gagan's Track 3 views
// (feature/community, commit 703938b) into the chat: the toggle sits on the latest results.
// Results always open as a list. The app can suggest the map, but only the parent switches.
// Comparing two schools happens in the chat (compare tray or "compare #1 and #2").
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./views.css";
import type { Actions } from "./blocks";
import { nameOf, statusLabel } from "./labels";
import { t, tn, uiLanguage } from "./i18n";
import type { Card, Criterion, ProgramPin } from "./types";

export type ResultsView = "list" | "map";

const SUGGEST_MAP_MILES = 10;

function milesBetween(a: [number, number], b: [number, number]) {
  const rad = Math.PI / 180;
  const dLat = (b[0] - a[0]) * rad;
  const dLon = (b[1] - a[1]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2;
  return 3958.8 * 2 * Math.asin(Math.sqrt(h));
}

function pointOf(card: Card): [number, number] | null {
  return card.lat != null && card.lon != null ? [card.lat, card.lon] : null;
}

/** Widest straight-line spread across the top 10 results, in miles. */
export function spreadMiles(cards: Card[]) {
  const points = cards.slice(0, 10).map(pointOf).filter((p): p is [number, number] => p !== null);
  let widest = 0;
  for (let i = 0; i < points.length; i += 1) {
    for (let j = i + 1; j < points.length; j += 1) widest = Math.max(widest, milesBetween(points[i], points[j]));
  }
  return widest;
}

export function ViewToggle(props: {
  view: ResultsView;
  onChange: (view: ResultsView) => void;
  cards: Card[];
  criteria: Criterion[];
  children: Record<ResultsView, ReactNode>;
}) {
  const spread = useMemo(() => spreadMiles(props.cards), [props.cards]);
  const aboutPlace = props.criteria.some((item) => item.kind === "distance");
  const suggestMap = props.view !== "map" && props.cards.length > 1 && (aboutPlace || spread > SUGGEST_MAP_MILES);
  const tabs: [ResultsView, string][] = [["list", t("views.list")], ["map", t("views.map")]];

  return (
    <section className="results-views">
      <div className="view-tabs" role="tablist" aria-label={t("views.label")}>
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={props.view === id} onClick={() => props.onChange(id)}>
            {label}
          </button>
        ))}
      </div>
      {suggestMap && (
        <p className="map-hint">
          {aboutPlace
            ? t("views.hint_distance")
            : t("views.hint_spread", { n: Math.round(spread) })}{" "}
          <button className="texty" onClick={() => props.onChange("map")}>{t("views.show_map")}</button>
        </p>
      )}
      <div role="tabpanel" aria-label={tabs.find(([id]) => id === props.view)?.[1]}>
        {props.children[props.view]}
      </div>
    </section>
  );
}

function pinColor(card: Card) {
  if (card.missed_must) return "var(--attention)";
  if (card.match >= 0.85) return "var(--confirmed)";
  if (card.match >= 0.65) return "var(--partial)";
  return "var(--attention)";
}

const escapeHtml = (text: string) =>
  text.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] as string);

type Placed = { card: Card; rank: number | null; hollow: boolean };

export function MapView(props: {
  schools: Card[];
  gaps: Card[];
  missed: Card[];
  criteria: Criterion[];
  center: [number, number] | null;
  programs: ProgramPin[];
  actions: Actions;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const { send, busy, picked, setPicked } = props.actions;

  // Numbers match the list. "Missing a fact" schools are plain pins; missed must-haves are hollow.
  const ranked = useMemo<Placed[]>(
    () => [
      ...props.schools.map((card, index) => ({ card, rank: index + 1, hollow: false })),
      ...props.gaps.map((card) => ({ card, rank: null, hollow: false })),
      ...props.missed.map((card) => ({ card, rank: null, hollow: true })),
    ],
    [props.schools, props.gaps, props.missed],
  );
  const placed = ranked.filter((row) => pointOf(row.card));
  const unplaced = ranked.length - placed.length;
  const labels = useMemo(() => new Map(props.criteria.map((item) => [item.id, nameOf(item)])), [props.criteria]);
  const byId = useMemo(() => new Map(ranked.map((row) => [row.card.id, row])), [ranked]);

  useEffect(() => {
    if (!box.current || map.current) return;
    map.current = L.map(box.current, { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const current = map.current;
    const group = layer.current;
    if (!current || !group) return;
    group.clearLayers();
    const bounds: L.LatLngExpression[] = [];
    if (props.center) {
      L.marker(props.center, {
        icon: L.divIcon({ className: "pin-you", html: `<span>${escapeHtml(t("views.search_area"))}</span>`, iconSize: [96, 24], iconAnchor: [48, 12] }),
        keyboard: false,
        interactive: false,
      }).addTo(group);
      bounds.push(props.center);
    }
    // Programs first, so school pins sit on top of the dashed lines.
    for (const program of props.programs) {
      const point: [number, number] = [program.lat, program.lon];
      const fills = program.links
        .map((link) => {
          const row = byId.get(link.school_id);
          if (!row) return null;
          const where = row.rank ? `#${row.rank}` : row.card.name;
          return t("views.program_fills", { need: labels.get(link.criterion_id) ?? t("views.a_need"), where, miles: link.miles });
        })
        .filter(Boolean);
      for (const link of program.links) {
        const school = byId.get(link.school_id);
        const schoolPoint = school && pointOf(school.card);
        if (schoolPoint) L.polyline([schoolPoint, point], { className: "program-link", interactive: false }).addTo(group);
      }
      L.marker(point, {
        icon: L.divIcon({ className: "pin-wrap", html: '<span class="pin-program">◆</span>', iconSize: [22, 22], iconAnchor: [11, 11] }),
        title: t("views.nearby_program", { name: program.name }),
        alt: t("views.nearby_program", { name: program.name }),
      })
        .bindTooltip(`<strong>${escapeHtml(t("views.nearby_program", { name: program.name }))}</strong><br>${fills.map((line) => escapeHtml(String(line))).join("<br>")}`)
        .addTo(group);
      bounds.push(point);
    }
    for (const row of placed) {
      const point = pointOf(row.card) as [number, number];
      const label = row.rank ?? "";
      const html = row.hollow
        ? `<span class="pin hollow" style="border-color:${pinColor(row.card)}">${label}</span>`
        : `<span class="pin" style="background:${pinColor(row.card)}">${label}</span>`;
      const marker = L.marker(point, {
        icon: L.divIcon({ className: "pin-wrap", html, iconSize: [30, 30], iconAnchor: [15, 15] }),
        title: `${row.rank ? `${row.rank}. ` : ""}${t("views.pin_title", { name: row.card.name, pct: Math.round(row.card.match * 100) })}${row.hollow ? `, ${t("views.pin_missed")}` : ""}`,
        alt: row.card.name,
        riseOnHover: true,
      });
      marker.on("click", () => setSelected(row.card.id));
      marker.addTo(group);
      bounds.push(point);
    }
    if (bounds.length > 1) current.fitBounds(L.latLngBounds(bounds), { padding: [36, 36], maxZoom: 13 });
    else if (bounds.length === 1) current.setView(bounds[0], 12);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    // uiLanguage(): rebuild the pins' titles and tooltips when the UI language changes.
  }, [props.schools, props.gaps, props.missed, props.center, props.programs, uiLanguage()]);

  useEffect(() => {
    // The map can be created before the chat lays it out; recompute its size once it has one.
    const handle = setTimeout(() => map.current?.invalidateSize(), 50);
    return () => clearTimeout(handle);
  }, []);

  const chosen = selected ? byId.get(selected) ?? null : null;
  const chosenPrograms = chosen
    ? props.programs.flatMap((program) =>
        program.links.filter((link) => link.school_id === chosen.card.id).map((link) => ({ program, link })),
      )
    : [];
  const isPicked = chosen ? picked.some((item) => item.id === chosen.card.id) : false;

  return (
    <div className="map-view">
      <p className="meta">
        {tn("views.on_map", placed.length)} {t("views.numbers")}
        {props.programs.length > 0 ? ` ${t("views.programs_note")}` : ""}
        {unplaced > 0 ? ` ${tn("views.unplaced", unplaced)}` : ""}
      </p>
      <div className="map-box" ref={box} aria-label={t("views.map_label")} role="region" />
      <ul className="map-legend" aria-hidden="true">
        <li><span className="dot" style={{ background: "var(--confirmed)" }} /> {t("views.legend_high")}</li>
        <li><span className="dot" style={{ background: "var(--partial)" }} /> {t("views.legend_mid")}</li>
        <li><span className="dot" style={{ background: "var(--attention)" }} /> {t("views.legend_low")}</li>
        <li><span className="dot hollow" /> {t("views.legend_missed")}</li>
        {props.programs.length > 0 && <li><span className="legend-program">◆</span> {t("views.legend_program")}</li>}
      </ul>
      {chosen && (
        <article className="pin-card" aria-live="polite" data-school-id={chosen.card.id}>
          <header>
            <h3>
              {chosen.rank ? `${chosen.rank}. ` : ""}
              {chosen.card.name}
            </h3>
            <button className="icon" aria-label={t("views.close")} onClick={() => setSelected(null)}>×</button>
          </header>
          <p className="meta">
            {t("views.pin_meta", { pct: Math.round(chosen.card.match * 100), verified: chosen.card.verified })}
            {chosen.card.distance_miles != null ? ` · ${t("blocks.miles", { n: chosen.card.distance_miles })}` : ""}
            {chosen.hollow ? ` · ${t("views.pin_missed")}` : ""}
          </p>
          <ul className="pin-evidence">
            {chosen.card.evidence.map((row) => (
              <li key={row.criterion_id}>
                <span className={`pill ${row.status}`}>{statusLabel(row.status)}</span>{" "}
                {labels.get(row.criterion_id) ?? row.criterion_id}
              </li>
            ))}
            {chosenPrograms.map(({ program, link }) => (
              <li key={`${program.id}-${link.criterion_id}`} className="pin-program-line">
                {t("views.pin_program", { name: program.name, miles: link.miles, need: (labels.get(link.criterion_id) ?? t("views.a_need")).toLowerCase() })}
              </li>
            ))}
          </ul>
          <div className="row-actions">
            <button disabled={busy} onClick={() => send({ action: "school_detail", school_ids: [chosen.card.id] })}>{t("views.details")}</button>
            <button disabled={busy} onClick={() => send({ action: "save", school_ids: [chosen.card.id] })}>{t("blocks.save")}</button>
            <button
              aria-pressed={isPicked}
              onClick={() =>
                setPicked(
                  isPicked
                    ? picked.filter((item) => item.id !== chosen.card.id)
                    : [...picked, { id: chosen.card.id, name: chosen.card.name }].slice(-2),
                )
              }
            >
              {isPicked ? t("blocks.selected") : t("blocks.compare")}
            </button>
          </div>
        </article>
      )}
    </div>
  );
}
