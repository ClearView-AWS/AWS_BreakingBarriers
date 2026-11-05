import "./school-gallery.css";
import { t } from "../i18n";

export function SchoolGallery({ schoolName }: { schoolName: string }) {
  return (
    <section className="school-gallery" aria-label={t("school_gallery.aria", { school: schoolName })}>
      <div className="school-gallery-heading">
        <h3>{t("school_gallery.title")}</h3>
        <span>{t("school_gallery.illustrative")}</span>
      </div>
      <div className="school-gallery-grid">
        <div className="school-gallery-scene school-gallery-campus">
          <svg viewBox="0 0 800 500" aria-hidden="true">
            <defs>
              <linearGradient id="campus-sky" x2="0" y2="1">
                <stop stopColor="#b8e3f0" />
                <stop offset="1" stopColor="#f4ead0" />
              </linearGradient>
              <linearGradient id="campus-wall" x2="0" y2="1">
                <stop stopColor="#f7e6c6" />
                <stop offset="1" stopColor="#e9c99c" />
              </linearGradient>
            </defs>
            <rect width="800" height="500" fill="url(#campus-sky)" />
            <circle cx="650" cy="92" r="44" fill="#ffd47b" />
            <path d="M0 346 Q170 300 325 350 T800 332 V500 H0Z" fill="#8dbf85" />
            <path d="M112 233 397 116l288 117v28H112Z" fill="#617b76" />
            <rect x="139" y="242" width="520" height="176" rx="8" fill="url(#campus-wall)" />
            <rect x="355" y="286" width="92" height="132" rx="5" fill="#66827e" />
            <circle cx="421" cy="354" r="4" fill="#f3d37e" />
            <g fill="#9dcbd2" stroke="#fff4dd" strokeWidth="9">
              <rect x="176" y="273" width="70" height="66" rx="4" />
              <rect x="274" y="273" width="52" height="66" rx="4" />
              <rect x="475" y="273" width="52" height="66" rx="4" />
              <rect x="552" y="273" width="70" height="66" rx="4" />
              <rect x="176" y="361" width="70" height="42" rx="4" />
              <rect x="274" y="361" width="52" height="42" rx="4" />
              <rect x="475" y="361" width="52" height="42" rx="4" />
              <rect x="552" y="361" width="70" height="42" rx="4" />
            </g>
            <g fill="#477c57">
              <circle cx="87" cy="295" r="66" />
              <circle cx="715" cy="300" r="76" />
              <circle cx="754" cy="335" r="48" />
            </g>
            <g fill="#8c644a">
              <rect x="79" y="320" width="16" height="90" />
              <rect x="706" y="328" width="18" height="90" />
            </g>
            <path d="M0 420 Q220 395 397 423 T800 414V500H0Z" fill="#6ba66a" />
            <path d="M400 418 345 500h145Z" fill="#d7c39e" />
          </svg>
          <span>{t("school_gallery.campus")}</span>
        </div>
        <div className="school-gallery-scene">
          <svg viewBox="0 0 500 300" aria-hidden="true">
            <rect width="500" height="300" fill="#f1dfbf" />
            <rect x="28" y="28" width="170" height="130" rx="8" fill="#fff5df" />
            <rect x="41" y="41" width="144" height="104" rx="4" fill="#a8d7dc" />
            <path d="M113 41v104M41 94h144" stroke="#fff5df" strokeWidth="8" />
            <path d="M0 207h500v93H0Z" fill="#c38d62" />
            <rect x="248" y="48" width="211" height="114" rx="7" fill="#829d83" />
            <rect x="265" y="65" width="176" height="80" rx="3" fill="#e7edcc" />
            <path d="M280 83h140M280 102h112M280 121h128" stroke="#91a88b" strokeWidth="7" strokeLinecap="round" />
            <path d="M108 209v-23h170v23m-149 0 11 91m106-91-12 91" fill="#7b5946" stroke="#7b5946" strokeWidth="8" />
            <path d="M130 186h124l-10 33H140Z" fill="#d8a16b" />
            <circle cx="160" cy="173" r="16" fill="#f1c96e" />
            <circle cx="222" cy="174" r="15" fill="#8db8cc" />
          </svg>
          <span>{t("school_gallery.learning")}</span>
        </div>
        <div className="school-gallery-scene">
          <svg viewBox="0 0 500 300" aria-hidden="true">
            <rect width="500" height="300" fill="#c6e4e6" />
            <circle cx="400" cy="66" r="34" fill="#ffd47b" />
            <path d="M0 174Q108 126 222 173t278-4v131H0Z" fill="#8ab882" />
            <path d="M0 216Q150 185 280 221t220-5v84H0Z" fill="#6ca46f" />
            <path d="M106 204V94h14v110m-36-80h58l-9-23H79Z" fill="#b56850" />
            <path d="M286 222V113h14v109m-36-77h58l-9-23h-44Z" fill="#6b8790" />
            <path d="M178 225V176h12v49m-22-35h32l-7-15h-18Z" fill="#d79359" />
            <g fill="#477c57">
              <circle cx="70" cy="148" r="39" />
              <circle cx="438" cy="164" r="46" />
            </g>
            <g fill="#8c644a">
              <rect x="66" y="170" width="9" height="54" />
              <rect x="434" y="184" width="10" height="50" />
            </g>
          </svg>
          <span>{t("school_gallery.outdoors")}</span>
        </div>
      </div>
      <p className="school-gallery-note">{t("school_gallery.note")}</p>
    </section>
  );
}
