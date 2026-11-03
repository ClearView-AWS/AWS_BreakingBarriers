import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Card, Criterion } from "./types";

// Results always open as a list. Grid and Map are one tap away. The agent can
// suggest the map, but only the parent switches views.
export type ResultsView = "list" | "grid" | "map";

const STATUS_LABEL: Record<string, string> = {
  confirmed: "Confirmed",
  partial: "Partial",
  needs_attention: "Needs attention",
  unknown: "Unknown",
};

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
  const tabs: [ResultsView, string][] = [["list", "List"], ["grid", "Grid"], ["map", "Map"]];

  return (
    <section className="results-views">
      <div className="view-tabs" role="tablist" aria-label="Results view">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={props.view === id}
            aria-controls={`view-${id}`}
            onClick={() => props.onChange(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {suggestMap && (
        <p className="map-hint">
          {aboutPlace
            ? "You mentioned distance, so the map may help."
            : `These schools are spread across about ${Math.round(spread)} miles, so the map may help.`}{" "}
          <button className="texty" onClick={() => props.onChange("map")}>Show map</button>
        </p>
      )}
      <div id={`view-${props.view}`} role="tabpanel">
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

export function MapView(props: {
  cards: Card[];
  missed: Card[];
  criteria: Criterion[];
  center: [number, number] | null;
  cityLabel?: string | null;
  picked: string[];
  onPick: (ids: string[]) => void;
  onOpen: (id: string) => void;
  onSave: (id: string) => void;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const ranked = useMemo(
    () => [
      ...props.cards.map((card, index) => ({ card, rank: index + 1, hollow: false })),
      ...props.missed.map((card) => ({ card, rank: null as number | null, hollow: true })),
    ],
    [props.cards, props.missed],
  );
  const placed = ranked.filter((row) => pointOf(row.card));
  const unplaced = ranked.length - placed.length;

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
        icon: L.divIcon({ className: "pin-you", html: "<span>Search area</span>", iconSize: [96, 24], iconAnchor: [48, 12] }),
        keyboard: false,
        interactive: false,
      }).addTo(group);
      bounds.push(props.center);
    }
    for (const row of placed) {
      const point = pointOf(row.card) as [number, number];
      const label = row.rank ?? "";
      const html = row.hollow
        ? `<span class="pin hollow" style="border-color:${pinColor(row.card)}">${label}</span>`
        : `<span class="pin" style="background:${pinColor(row.card)}">${label}</span>`;
      const marker = L.marker(point, {
        icon: L.divIcon({ className: "pin-wrap", html, iconSize: [30, 30], iconAnchor: [15, 15] }),
        title: `${row.rank ? `${row.rank}. ` : ""}${row.card.name}, ${Math.round(row.card.match * 100)}% match${row.hollow ? ", missed a must-have" : ""}`,
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
  }, [props.cards, props.missed, props.center]);

  useEffect(() => {
    // The map is created while hidden on first paint in some layouts; recompute its size.
    const handle = setTimeout(() => map.current?.invalidateSize(), 50);
    return () => clearTimeout(handle);
  }, []);

  const chosen = ranked.find((row) => row.card.id === selected) ?? null;
  const labels = new Map(props.criteria.map((item) => [item.id, item.text]));

  return (
    <div className="map-view">
      <p className="meta">
        {placed.length} school{placed.length === 1 ? "" : "s"} on the map
        {props.cityLabel ? `, around ${props.cityLabel}` : ""}. Numbers match the list. Hollow pins missed a must-have.
        {unplaced > 0 ? ` ${unplaced} school${unplaced === 1 ? " has" : "s have"} no map point and ${unplaced === 1 ? "is" : "are"} only in the list.` : ""}
      </p>
      <div className="map-box" ref={box} aria-label="Map of the schools in the list" role="region" />
      <ul className="map-legend" aria-hidden="true">
        <li><span className="dot" style={{ background: "var(--confirmed)" }} /> 85%+ match</li>
        <li><span className="dot" style={{ background: "var(--partial)" }} /> 65 to 84%</li>
        <li><span className="dot" style={{ background: "var(--attention)" }} /> under 65%</li>
        <li><span className="dot hollow" /> missed a must-have</li>
      </ul>
      {chosen && (
        <article className="pin-card" aria-live="polite">
          <header>
            <h3>
              {chosen.rank ? `${chosen.rank}. ` : ""}
              {chosen.card.name}
            </h3>
            <button className="icon" aria-label="Close" onClick={() => setSelected(null)}>×</button>
          </header>
          <p className="meta">
            {Math.round(chosen.card.match * 100)}% match · Verified {chosen.card.verified}
            {chosen.card.distance_miles != null ? ` · ${chosen.card.distance_miles} miles` : ""}
            {chosen.hollow ? " · missed a must-have" : ""}
          </p>
          <ul className="pin-evidence">
            {chosen.card.evidence.map((row) => (
              <li key={row.criterion_id}>
                <span className={`pill ${row.status}`}>{STATUS_LABEL[row.status] ?? row.status}</span>{" "}
                {labels.get(row.criterion_id) ?? row.criterion_id}
              </li>
            ))}
          </ul>
          <div className="row-actions">
            <button onClick={() => props.onOpen(chosen.card.id)}>Details</button>
            <button onClick={() => props.onSave(chosen.card.id)}>Save</button>
            <button
              aria-pressed={props.picked.includes(chosen.card.id)}
              onClick={() =>
                props.onPick(
                  props.picked.includes(chosen.card.id)
                    ? props.picked.filter((id) => id !== chosen.card.id)
                    : [...props.picked, chosen.card.id].slice(-2),
                )
              }
            >
              {props.picked.includes(chosen.card.id) ? "Selected" : "Compare"}
            </button>
          </div>
        </article>
      )}
    </div>
  );
}
