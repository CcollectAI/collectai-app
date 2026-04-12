// ═══════════════════════════════════════════════════════════════════════════
// App Store Screenshot — Static compositions for iOS/Android store listings
// Renders a mock phone screen with marketing copy and device frame
// Usage: npx remotion still AppStoreScreenshot-1 --output=screenshots/01-collection.png
// ═══════════════════════════════════════════════════════════════════════════

import React from "react";
import { AbsoluteFill } from "remotion";
import { Colors, Fonts } from "../data/theme";
import { AppLogo } from "../components/Branding";

// ─── Types ──────────────────────────────────────────────────────────────

export interface ScreenshotProps {
  headline: string;
  subheadline: string;
  /** Which mock screen to render inside the device frame */
  screenType:
    | "collection"
    | "quickscan"
    | "item-detail"
    | "marketplace"
    | "deals"
    | "home";
  accentColor?: string;
  badgeText?: string;
}

// ─── iPhone Device Frame ────────────────────────────────────────────────

const DeviceFrame: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      width: 340,
      height: 696,
      borderRadius: 40,
      border: "6px solid #1A1A1A",
      backgroundColor: "#000",
      overflow: "hidden",
      position: "relative",
      boxShadow: "0 20px 80px rgba(0,0,0,0.35), 0 4px 20px rgba(0,0,0,0.2)",
    }}
  >
    {/* Dynamic Island */}
    <div
      style={{
        position: "absolute",
        top: 10,
        left: "50%",
        transform: "translateX(-50%)",
        width: 100,
        height: 28,
        borderRadius: 14,
        backgroundColor: "#000",
        zIndex: 10,
      }}
    />
    {/* Screen content */}
    <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
      {children}
    </div>
  </div>
);

// ─── Mock Screens ───────────────────────────────────────────────────────

const StatusBar: React.FC = () => (
  <div
    style={{
      height: 48,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "0 20px",
      fontSize: 13,
      fontWeight: 600,
      color: Colors.textPrimary,
      fontFamily: Fonts.body,
    }}
  >
    <span>9:41</span>
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <span style={{ fontSize: 11 }}>5G</span>
      <div style={{ width: 22, height: 11, border: `1.5px solid ${Colors.textPrimary}`, borderRadius: 3, position: "relative" }}>
        <div style={{ position: "absolute", left: 1.5, top: 1.5, bottom: 1.5, width: "70%", backgroundColor: Colors.success, borderRadius: 1 }} />
      </div>
    </div>
  </div>
);

const CollectionScreen: React.FC = () => (
  <div style={{ backgroundColor: Colors.background, height: "100%", fontFamily: Fonts.body }}>
    <StatusBar />
    <div style={{ padding: "8px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 20, fontWeight: 800, color: Colors.textPrimary, fontFamily: Fonts.heading }}>My Collection</span>
        <div style={{ backgroundColor: `${Colors.primary}15`, borderRadius: 12, padding: "4px 10px" }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: Colors.primary }}>142 items</span>
        </div>
      </div>
      {/* Portfolio value card */}
      <div style={{ background: `linear-gradient(135deg, ${Colors.primary}, ${Colors.primaryDark})`, borderRadius: 16, padding: "14px 16px", marginBottom: 12 }}>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.8)", fontWeight: 500, textTransform: "uppercase" as const, letterSpacing: 1 }}>Total Value</span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 2 }}>
          <span style={{ fontSize: 28, fontWeight: 900, color: "#fff", fontFamily: Fonts.mono }}>€24,850</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: Colors.success }}>+12.4%</span>
        </div>
      </div>
      {/* Grid */}
      <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 8 }}>
        {[
          { emoji: "🔮", name: "Charizard VMAX", val: "€380" },
          { emoji: "🧱", name: "Millennium Falcon", val: "€1,200" },
          { emoji: "👾", name: "Darth Maul #09", val: "€850" },
          { emoji: "⌚", name: "Speedmaster Pro", val: "€7,200" },
          { emoji: "🎵", name: "Kind of Blue OG", val: "€420" },
          { emoji: "👟", name: "Jordan 1 Chicago", val: "€3,100" },
        ].map((item, i) => (
          <div key={i} style={{ width: "47%", backgroundColor: Colors.surface, borderRadius: 12, padding: 10, border: `1px solid ${Colors.textSecondary}15` }}>
            <div style={{ width: "100%", height: 70, borderRadius: 8, background: `linear-gradient(135deg, ${Colors.primary}12, ${Colors.primary}06)`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 6 }}>
              <span style={{ fontSize: 28 }}>{item.emoji}</span>
            </div>
            <span style={{ fontSize: 10, fontWeight: 600, color: Colors.textPrimary, display: "block" }}>{item.name}</span>
            <span style={{ fontSize: 11, fontWeight: 800, color: Colors.primary, fontFamily: Fonts.mono }}>{item.val}</span>
          </div>
        ))}
      </div>
    </div>
  </div>
);

const QuickScanScreen: React.FC = () => (
  <div style={{ backgroundColor: "#0A0A0A", height: "100%", fontFamily: Fonts.body, position: "relative" }}>
    <StatusBar />
    {/* Camera viewfinder */}
    <div style={{ position: "absolute", inset: 48, display: "flex", alignItems: "center", justifyContent: "center" }}>
      {/* Scanning frame corners */}
      <div style={{ width: 220, height: 220, position: "relative" }}>
        {[{ top: 0, left: 0 }, { top: 0, right: 0 }, { bottom: 0, left: 0 }, { bottom: 0, right: 0 }].map((pos, i) => (
          <div key={i} style={{ position: "absolute", ...pos, width: 40, height: 40, borderColor: Colors.primary, borderStyle: "solid", borderWidth: 0, ...(i < 2 ? { borderTopWidth: 3 } : { borderBottomWidth: 3 }), ...(i % 2 === 0 ? { borderLeftWidth: 3 } : { borderRightWidth: 3 }), borderRadius: i === 0 ? "8px 0 0 0" : i === 1 ? "0 8px 0 0" : i === 2 ? "0 0 0 8px" : "0 0 8px 0" }} />
        ))}
        {/* Item placeholder */}
        <div style={{ position: "absolute", inset: 30, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 64 }}>🔮</span>
        </div>
      </div>
      {/* Scan line */}
      <div style={{ position: "absolute", top: "45%", left: 80, right: 80, height: 2, backgroundColor: Colors.primary, opacity: 0.7, boxShadow: `0 0 20px ${Colors.primary}` }} />
    </div>
    {/* Bottom panel */}
    <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, background: "linear-gradient(transparent, rgba(0,0,0,0.9))", padding: "40px 20px 24px" }}>
      <div style={{ backgroundColor: "rgba(255,255,255,0.1)", borderRadius: 16, padding: "12px 16px", backdropFilter: "blur(10px)" }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: Colors.primary }}>AI Scanning...</span>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", display: "block", marginTop: 2 }}>Point camera at any collectible</span>
      </div>
    </div>
  </div>
);

const ItemDetailScreen: React.FC = () => (
  <div style={{ backgroundColor: Colors.background, height: "100%", fontFamily: Fonts.body }}>
    <StatusBar />
    <div style={{ padding: "4px 16px" }}>
      {/* Item image area */}
      <div style={{ width: "100%", height: 180, borderRadius: 16, background: `linear-gradient(135deg, ${Colors.primary}15, ${Colors.primaryDark}10)`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 10 }}>
        <span style={{ fontSize: 72 }}>🔮</span>
      </div>
      <span style={{ fontSize: 16, fontWeight: 800, color: Colors.textPrimary }}>Charizard VMAX #074</span>
      <div style={{ display: "flex", gap: 6, marginTop: 4, marginBottom: 10 }}>
        <div style={{ backgroundColor: `${Colors.pokemon}20`, borderRadius: 6, padding: "2px 8px" }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: Colors.pokemon }}>Pokemon TCG</span>
        </div>
        <div style={{ backgroundColor: `${Colors.success}20`, borderRadius: 6, padding: "2px 8px" }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: Colors.success }}>NM/Mint</span>
        </div>
      </div>
      {/* Price card */}
      <div style={{ background: `linear-gradient(135deg, ${Colors.primary}, ${Colors.primaryDark})`, borderRadius: 14, padding: 14, marginBottom: 10 }}>
        <span style={{ fontSize: 9, color: "rgba(255,255,255,0.8)", textTransform: "uppercase" as const, letterSpacing: 1 }}>AI Valuation</span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 2 }}>
          <span style={{ fontSize: 28, fontWeight: 900, color: "#fff", fontFamily: Fonts.mono }}>€380</span>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.7)" }}>€320 — €450</span>
        </div>
      </div>
      {/* Market evidence */}
      <span style={{ fontSize: 11, fontWeight: 700, color: Colors.textSecondary, textTransform: "uppercase" as const, letterSpacing: 1, marginBottom: 6, display: "block" }}>Market Evidence (14 sold)</span>
      {[
        { src: "eBay", price: "€395", when: "2d ago" },
        { src: "TCGPlayer", price: "€362", when: "4d ago" },
        { src: "Cardmarket", price: "€410", when: "1w ago" },
      ].map((comp, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: Colors.surface, borderRadius: 10, padding: "8px 12px", marginBottom: 4, border: `1px solid ${Colors.textSecondary}10` }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: Colors.textPrimary }}>{comp.src}</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12, fontWeight: 800, color: Colors.primary, fontFamily: Fonts.mono }}>{comp.price}</span>
            <span style={{ fontSize: 9, color: Colors.textSecondary }}>{comp.when}</span>
          </div>
        </div>
      ))}
    </div>
  </div>
);

const MarketplaceScreen: React.FC = () => (
  <div style={{ backgroundColor: Colors.background, height: "100%", fontFamily: Fonts.body }}>
    <StatusBar />
    <div style={{ padding: "8px 16px" }}>
      <span style={{ fontSize: 20, fontWeight: 800, color: Colors.textPrimary, fontFamily: Fonts.heading, display: "block", marginBottom: 8 }}>Marketplace</span>
      {/* Search bar */}
      <div style={{ backgroundColor: Colors.surface, borderRadius: 12, padding: "10px 14px", marginBottom: 10, border: `1px solid ${Colors.textSecondary}15`, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 14, color: Colors.textSecondary }}>🔍</span>
        <span style={{ fontSize: 12, color: Colors.textSecondary }}>Search 37 marketplaces...</span>
      </div>
      {/* Results */}
      {[
        { title: "Charizard VMAX Rainbow", src: "eBay", price: "€395", img: "🔮", condition: "NM" },
        { title: "LEGO Star Destroyer 75252", src: "BrickLink", price: "€680", img: "🧱", condition: "NISB" },
        { title: "Rolex Submariner Date", src: "Chrono24", price: "€12,400", img: "⌚", condition: "Excellent" },
        { title: "Jordan 1 Retro High OG", src: "StockX", price: "€310", img: "👟", condition: "DS" },
        { title: "Black Lotus Beta", src: "TCGPlayer", price: "€28,500", img: "🪴", condition: "LP" },
      ].map((item, i) => (
        <div key={i} style={{ display: "flex", gap: 10, backgroundColor: Colors.surface, borderRadius: 12, padding: 10, marginBottom: 6, border: `1px solid ${Colors.textSecondary}10` }}>
          <div style={{ width: 56, height: 56, borderRadius: 10, background: `linear-gradient(135deg, ${Colors.primary}12, ${Colors.primary}06)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <span style={{ fontSize: 24 }}>{item.img}</span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: Colors.textPrimary, display: "block", overflow: "hidden", whiteSpace: "nowrap" as const, textOverflow: "ellipsis" as const }}>{item.title}</span>
            <div style={{ display: "flex", gap: 4, marginTop: 2 }}>
              <span style={{ fontSize: 9, color: Colors.primary, fontWeight: 600 }}>{item.src}</span>
              <span style={{ fontSize: 9, color: Colors.textSecondary }}>· {item.condition}</span>
            </div>
            <span style={{ fontSize: 14, fontWeight: 800, color: Colors.textPrimary, fontFamily: Fonts.mono, marginTop: 2, display: "block" }}>{item.price}</span>
          </div>
        </div>
      ))}
    </div>
  </div>
);

const DealsScreen: React.FC = () => (
  <div style={{ backgroundColor: Colors.background, height: "100%", fontFamily: Fonts.body }}>
    <StatusBar />
    <div style={{ padding: "8px 16px" }}>
      <span style={{ fontSize: 20, fontWeight: 800, color: Colors.textPrimary, fontFamily: Fonts.heading, display: "block", marginBottom: 8 }}>Deal Discovery</span>
      {/* Active mandate */}
      <div style={{ background: `linear-gradient(135deg, ${Colors.success}12, ${Colors.success}05)`, borderRadius: 14, padding: 12, border: `1px solid ${Colors.success}30`, marginBottom: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: Colors.success }}>3 new deals found</span>
          <span style={{ fontSize: 9, color: Colors.textSecondary }}>2 min ago</span>
        </div>
      </div>
      {[
        { title: "LEGO Cafe Corner 10182", market: "€4,200", found: "€2,800", save: "33%", src: "eBay" },
        { title: "PSA 10 Base Set Zard", market: "€42,000", found: "€38,500", save: "8%", src: "Mercari" },
        { title: "Omega Speedmaster 321", market: "€14,200", found: "€11,900", save: "16%", src: "Chrono24" },
      ].map((deal, i) => (
        <div key={i} style={{ backgroundColor: Colors.surface, borderRadius: 12, padding: 12, marginBottom: 6, border: `1px solid ${Colors.textSecondary}10` }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: Colors.textPrimary, display: "block" }}>{deal.title}</span>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
            <div>
              <span style={{ fontSize: 9, color: Colors.textSecondary, display: "block" }}>Market Value</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: Colors.textSecondary, textDecoration: "line-through" as const }}>{deal.market}</span>
            </div>
            <div>
              <span style={{ fontSize: 9, color: Colors.success, display: "block" }}>Found Price</span>
              <span style={{ fontSize: 14, fontWeight: 800, color: Colors.success, fontFamily: Fonts.mono }}>{deal.found}</span>
            </div>
            <div style={{ backgroundColor: `${Colors.error}15`, borderRadius: 8, padding: "4px 8px" }}>
              <span style={{ fontSize: 11, fontWeight: 800, color: Colors.error }}>-{deal.save}</span>
            </div>
          </div>
          <span style={{ fontSize: 9, color: Colors.primary, fontWeight: 600, marginTop: 4, display: "block" }}>via {deal.src}</span>
        </div>
      ))}
    </div>
  </div>
);

const HomeScreen: React.FC = () => (
  <div style={{ backgroundColor: Colors.background, height: "100%", fontFamily: Fonts.body }}>
    <StatusBar />
    <div style={{ padding: "8px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <span style={{ fontSize: 13, color: Colors.textSecondary }}>Good morning</span>
          <span style={{ fontSize: 20, fontWeight: 800, color: Colors.textPrimary, fontFamily: Fonts.heading, display: "block" }}>Collector</span>
        </div>
        <AppLogo size={36} />
      </div>
      {/* Stats row */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {[
          { label: "Items", value: "142", color: Colors.primary },
          { label: "Value", value: "€24.8K", color: Colors.success },
          { label: "Alerts", value: "3", color: Colors.warning },
        ].map((s, i) => (
          <div key={i} style={{ flex: 1, backgroundColor: Colors.surface, borderRadius: 12, padding: "10px 12px", border: `1px solid ${Colors.textSecondary}10` }}>
            <span style={{ fontSize: 9, color: Colors.textSecondary, textTransform: "uppercase" as const, letterSpacing: 1 }}>{s.label}</span>
            <span style={{ fontSize: 18, fontWeight: 900, color: s.color, fontFamily: Fonts.mono, display: "block", marginTop: 2 }}>{s.value}</span>
          </div>
        ))}
      </div>
      {/* Trending */}
      <span style={{ fontSize: 14, fontWeight: 700, color: Colors.textPrimary, marginBottom: 6, display: "block" }}>Trending in Your Collection</span>
      {[
        { name: "Charizard VMAX", change: "+18%", emoji: "🔮" },
        { name: "LEGO Millennium Falcon", change: "+5%", emoji: "🧱" },
        { name: "Jordan 1 Chicago", change: "-3%", emoji: "👟" },
      ].map((t, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, backgroundColor: Colors.surface, borderRadius: 10, padding: "8px 12px", marginBottom: 4, border: `1px solid ${Colors.textSecondary}10` }}>
          <span style={{ fontSize: 20 }}>{t.emoji}</span>
          <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: Colors.textPrimary }}>{t.name}</span>
          <span style={{ fontSize: 12, fontWeight: 800, color: t.change.startsWith("+") ? Colors.success : Colors.error, fontFamily: Fonts.mono }}>{t.change}</span>
        </div>
      ))}
      {/* Categories */}
      <span style={{ fontSize: 14, fontWeight: 700, color: Colors.textPrimary, marginTop: 10, marginBottom: 6, display: "block" }}>Browse Categories</span>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" as const }}>
        {["🔮 Pokemon", "🧱 LEGO", "👾 Funko", "⌚ Watches", "👟 Sneakers", "🎵 Vinyl"].map((cat, i) => (
          <div key={i} style={{ backgroundColor: `${Colors.primary}10`, borderRadius: 10, padding: "6px 12px" }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: Colors.primary }}>{cat}</span>
          </div>
        ))}
      </div>
    </div>
  </div>
);

// ─── Screen map ─────────────────────────────────────────────────────────

const SCREENS: Record<ScreenshotProps["screenType"], React.FC> = {
  collection: CollectionScreen,
  quickscan: QuickScanScreen,
  "item-detail": ItemDetailScreen,
  marketplace: MarketplaceScreen,
  deals: DealsScreen,
  home: HomeScreen,
};

// ─── Main Composition ───────────────────────────────────────────────────

export const AppStoreScreenshot: React.FC<ScreenshotProps> = ({
  headline,
  subheadline,
  screenType,
  accentColor = Colors.primary,
  badgeText,
}) => {
  const ScreenComponent = SCREENS[screenType];

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${Colors.background} 0%, ${accentColor}08 100%)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        fontFamily: Fonts.heading,
      }}
    >
      {/* Top section — marketing copy */}
      <div
        style={{
          marginTop: 120,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          padding: "0 80px",
        }}
      >
        {badgeText && (
          <div
            style={{
              backgroundColor: `${accentColor}15`,
              border: `2px solid ${accentColor}40`,
              borderRadius: 20,
              padding: "6px 18px",
            }}
          >
            <span
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: accentColor,
                fontFamily: Fonts.heading,
              }}
            >
              {badgeText}
            </span>
          </div>
        )}
        <span
          style={{
            fontSize: 64,
            fontWeight: 900,
            color: Colors.textPrimary,
            textAlign: "center",
            lineHeight: 1.1,
            letterSpacing: -2,
          }}
        >
          {headline}
        </span>
        <span
          style={{
            fontSize: 28,
            fontWeight: 500,
            color: Colors.textSecondary,
            textAlign: "center",
            lineHeight: 1.3,
          }}
        >
          {subheadline}
        </span>
      </div>

      {/* Device frame with mock screen */}
      <div style={{ marginTop: 60, transform: "scale(1.6)", transformOrigin: "top center" }}>
        <DeviceFrame>
          <ScreenComponent />
        </DeviceFrame>
      </div>
    </AbsoluteFill>
  );
};
