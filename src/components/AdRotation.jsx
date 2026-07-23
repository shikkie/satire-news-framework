import { useEffect, useState } from "react";
import { adImageSrc, adLogoSrc, fetchAds, pickWeightedAd } from "../lib/ads.js";

const ROTATE_MS = 10000;

export default function AdRotation({ className = "" }) {
  const [ads, setAds] = useState([]);
  const [current, setCurrent] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const list = await fetchAds();
      if (!alive) return;
      setAds(list);
      setCurrent(pickWeightedAd(list));
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (ads.length < 2) return undefined;
    const id = setInterval(() => {
      setCurrent((prev) => pickWeightedAd(ads, prev?.slug));
    }, ROTATE_MS);
    return () => clearInterval(id);
  }, [ads]);

  if (!current) return null;

  const img = adImageSrc(current);
  const logo = adLogoSrc(current);
  const href =
    current.website ||
    (current.email ? `mailto:${current.email}` : undefined) ||
    (current.phone ? `tel:${current.phone.replace(/[^\d+]/g, "")}` : undefined);

  const inner = (
    <>
      <div className="ad-kicker">
        <span>Sponsored</span>
        <span className="ad-category">{current.category || "Local business"}</span>
      </div>
      <div className="ad-body">
        {img ? (
          <div className="ad-media">
            <img src={img} alt="" loading="lazy" />
          </div>
        ) : null}
        <div className="ad-copy">
          <div className="ad-title-row">
            {logo ? (
              <img className="ad-logo" src={logo} alt="" width={40} height={40} />
            ) : null}
            <div>
              <h3 className="ad-name">{current.name}</h3>
              {current.tagline ? (
                <p className="ad-tagline">{current.tagline}</p>
              ) : null}
            </div>
          </div>
          {current.bio ? (
            <p className="ad-bio">
              {current.bio.replace(/\s+/g, " ").replace(/[*#_]/g, "").slice(0, 180)}
              {current.bio.length > 180 ? "…" : ""}
            </p>
          ) : null}
          <ul className="ad-contact">
            {current.address ? <li>{current.address}</li> : null}
            {current.phone ? <li>{current.phone}</li> : null}
            {current.email ? <li>{current.email}</li> : null}
            {current.hours ? <li>{current.hours}</li> : null}
          </ul>
          {current.cta ? <span className="ad-cta">{current.cta}</span> : null}
        </div>
      </div>
    </>
  );

  return (
    <aside
      className={`ad-rotation ${className}`.trim()}
      aria-label="Sponsored advertisement"
    >
      {href ? (
        <a
          className="ad-card"
          href={href}
          target="_blank"
          rel="noopener noreferrer sponsored"
        >
          {inner}
        </a>
      ) : (
        <div className="ad-card">{inner}</div>
      )}
    </aside>
  );
}
