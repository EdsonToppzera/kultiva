import * as React from "react";
import { useTranslation } from "react-i18next";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import {
  AlertTriangle,
  ChevronLeft,
  Crosshair,
  Maximize2,
  Minimize2,
  Plus,
  X,
} from "lucide-react";
import { KultivaLogo } from "../components/KultivaLogo";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import kinks from "@turf/kinks";
import { polygon as turfPolygon } from "@turf/helpers";

export interface MapCoordinate {
  id: string;
  lat: number;
  lng: number;
}

export interface MapTerrainPageProps {
  initialName?: string;
  initialPoints?: MapCoordinate[];
  onSaveArea?: (
    points: MapCoordinate[],
    areaHectares: number,
    nomePropriedade: string
  ) => void;
  onBack?: () => void;
}

const DEFAULT_CENTER: [number, number] = [-4.1058, -38.6048];
const DEFAULT_ZOOM = 15;
const MAX_RECOMMENDED_AREA_SQ_METERS = 100_000; // 10 hectares

/**
 * Calcula a área aproximada em metros quadrados de um polígono geográfico
 * usando a fórmula esférica de excesso de área (Shoelace projetado na esfera).
 */
function calculatePolygonAreaSqMeters(points: MapCoordinate[]): number {
  if (points.length < 3) return 0;

  const earthRadius = 6_378_137;
  const toRad = (deg: number) => (deg * Math.PI) / 180;

  let total = 0;
  for (let i = 0; i < points.length; i++) {
    const current = points[i];
    const next = points[(i + 1) % points.length];
    const lat1 = toRad(current.lat);
    const lat2 = toRad(next.lat);
    const deltaLng = toRad(next.lng - current.lng);

    total += deltaLng * (2 + Math.sin(lat1) + Math.sin(lat2));
  }

  return Math.abs((total * earthRadius * earthRadius) / 2);
}

/**
 * Verifica se o contorno do polígono possui auto-intersecções (linhas cruzadas)
 * usando `@turf/kinks`.
 */
function detectPolygonSelfIntersections(points: MapCoordinate[]): {
  hasKinks: boolean;
  kinkCoords: [number, number][];
} {
  if (points.length < 4) {
    return { hasKinks: false, kinkCoords: [] };
  }

  try {
    const ring = points.map((p) => [p.lng, p.lat]);
    ring.push([points[0].lng, points[0].lat]);
    const poly = turfPolygon([ring]);
    const result = kinks(poly);
    const kinkCoords = result.features.map(
      (feat) => [feat.geometry.coordinates[1], feat.geometry.coordinates[0]] as [number, number]
    );
    return {
      hasKinks: kinkCoords.length > 0,
      kinkCoords,
    };
  } catch {
    return { hasKinks: false, kinkCoords: [] };
  }
}

function createVertexIcon(index: number): L.DivIcon {
  return L.divIcon({
    className: "kultiva-vertex-marker",
    html: `
      <div style="position: relative; width: 14px; height: 14px; transform: translate(-50%, -50%);">
        <div style="width: 14px; height: 14px; border-radius: 9999px; background: #511D4E; border: 2.5px solid #FFFFFF; box-shadow: 0 1px 4px rgba(0,0,0,0.45);"></div>
        <span style="position: absolute; left: 14px; top: -12px; color: #FFFFFF; font-size: 12px; font-weight: 700; text-shadow: 0 1px 3px rgba(0,0,0,0.85); pointer-events: none;">${index}</span>
      </div>
    `,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

interface MapControllerProps {
  onCenterChange: (center: { lat: number; lng: number }) => void;
  mapRef: React.MutableRefObject<L.Map | null>;
  isExpanded: boolean;
}

function MapController({
  onCenterChange,
  mapRef,
  isExpanded,
}: MapControllerProps) {
  const map = useMap();

  React.useEffect(() => {
    mapRef.current = map;
    const center = map.getCenter();
    onCenterChange({ lat: center.lat, lng: center.lng });
  }, [map, mapRef, onCenterChange]);

  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      map.invalidateSize();
    }, 150);
    return () => window.clearTimeout(timer);
  }, [isExpanded, map]);

  useMapEvents({
    move() {
      const center = map.getCenter();
      onCenterChange({ lat: center.lat, lng: center.lng });
    },
    moveend() {
      const center = map.getCenter();
      onCenterChange({ lat: center.lat, lng: center.lng });
    },
  });

  return null;
}

export function MapTerrainPage({
  initialName = "",
  initialPoints = [],
  onSaveArea,
  onBack,
}: MapTerrainPageProps) {
  const { t } = useTranslation();
  // Gestão clara do estado de coordenadas do polígono
  const [nomePropriedade, setNomePropriedade] = React.useState(initialName);
  const [points, setPoints] = React.useState<MapCoordinate[]>(initialPoints);
  const [mapCenter, setMapCenter] = React.useState<{
    lat: number;
    lng: number;
  }>(() =>
    initialPoints.length > 0
      ? { lat: initialPoints[0].lat, lng: initialPoints[0].lng }
      : {
          lat: DEFAULT_CENTER[0],
          lng: DEFAULT_CENTER[1],
        }
  );
  const [isMapExpanded, setIsMapExpanded] = React.useState(false);
  const [isLocating, setIsLocating] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);
  const [gpsError, setGpsError] = React.useState<string | null>(null);
  const [saveError, setSaveError] = React.useState<string | null>(null);

  const mapRef = React.useRef<L.Map | null>(null);

  const handleCenterChange = React.useCallback(
    (center: { lat: number; lng: number }) => {
      setMapCenter(center);
    },
    []
  );

  const handleUseCurrentLocation = () => {
    setGpsError(null);

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setGpsError(t("map.geolocationUnsupported"));
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setMapCenter({ lat: latitude, lng: longitude });
        mapRef.current?.flyTo([latitude, longitude], 17, { duration: 0.8 });
        setIsLocating(false);
      },
      () => {
        setGpsError(t("map.geolocationError"));
        setIsLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const handleMarkPinPoint = () => {
    const currentCenter = mapRef.current?.getCenter();
    const lat = currentCenter ? currentCenter.lat : mapCenter.lat;
    const lng = currentCenter ? currentCenter.lng : mapCenter.lng;

    const newPoint: MapCoordinate = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      lat,
      lng,
    };

    setPoints((prev) => [...prev, newPoint]);
  };

  const handleRemovePoint = (id: string) => {
    setPoints((prev) => prev.filter((point) => point.id !== id));
  };

  const areaSqMeters = React.useMemo(
    () => calculatePolygonAreaSqMeters(points),
    [points]
  );
  const areaHectares = areaSqMeters / 10_000;
  const selfIntersection = React.useMemo(
    () => detectPolygonSelfIntersections(points),
    [points]
  );
  const isAreaTooLarge =
    points.length >= 3 && areaSqMeters > MAX_RECOMMENDED_AREA_SQ_METERS;
  const canSave = points.length >= 3 && !selfIntersection.hasKinks;

  const polygonPositions = React.useMemo<[number, number][]>(
    () => points.map((point) => [point.lat, point.lng]),
    [points]
  );

  const handleSave = () => {
    if (!canSave || isSaving) return;
    setSaveError(null);
    setIsSaving(true);

    const resolvedName =
      nomePropriedade.trim() || t("map.defaultTerrainName");
    const areaPayload =
      areaHectares > 0 ? Number(areaHectares.toFixed(4)) : 0;

    try {
      onSaveArea?.(points, areaPayload, resolvedName);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F6F0] md:bg-[#EFECE3] md:py-6">
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pt-7 pb-8 text-[#1F1C18] md:min-h-[820px] md:rounded-[32px] md:border md:border-[#E6E4DA] md:shadow-sm">
        <div>
          <header className="flex items-center justify-between">
            <KultivaLogo />
          </header>

          <section className="mt-6">
            <h1 className="text-[30px] font-bold tracking-tight text-[#511D4E] leading-tight">
              {t("map.title")}
            </h1>
            <p className="mt-1.5 text-[15px] leading-snug text-[#6D6960]">
              {t("map.subtitle")}
            </p>
          </section>

          <section className="mt-4">
            <label
              htmlFor="nome-propriedade-input"
              className="block text-[11px] font-bold tracking-[0.08em] text-[#6D6960] uppercase"
            >
              {t("map.propertyNameLabel")}
            </label>
            <input
              id="nome-propriedade-input"
              type="text"
              value={nomePropriedade}
              onChange={(event) => setNomePropriedade(event.target.value)}
              placeholder={t("map.propertyNamePlaceholder")}
              className="mt-1.5 w-full rounded-2xl border border-[#D5D1C5] bg-white px-4 py-3 text-[15px] text-[#1F1C18] placeholder:text-[#9A958A] focus:border-[#511D4E] focus:outline-none focus:ring-2 focus:ring-[#511D4E]/15"
            />
          </section>

          {/* Mapa Interativo com Overlays */}
          <section className="mt-5">
            <div
              className={
                isMapExpanded
                  ? "fixed inset-0 z-50 bg-black"
                  : "relative h-72 w-full overflow-hidden rounded-2xl border border-[#E6E4DA] shadow-sm"
              }
            >
              <MapContainer
                center={DEFAULT_CENTER}
                zoom={DEFAULT_ZOOM}
                zoomControl={false}
                attributionControl={true}
                className="h-full w-full"
              >
                <TileLayer
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  attribution="Esri &middot; World Imagery"
                  maxZoom={19}
                />

                <MapController
                  onCenterChange={handleCenterChange}
                  mapRef={mapRef}
                  isExpanded={isMapExpanded}
                />

                {polygonPositions.length === 2 && (
                  <Polyline
                    positions={polygonPositions}
                    pathOptions={{ color: "#FFFFFF", weight: 2.5 }}
                  />
                )}

                {polygonPositions.length >= 3 && (
                  <Polygon
                    positions={polygonPositions}
                    pathOptions={{
                      color: selfIntersection.hasKinks ? "#C42311" : "#FFFFFF",
                      weight: 2.5,
                      fillColor: selfIntersection.hasKinks ? "#C42311" : "#FFFFFF",
                      fillOpacity: selfIntersection.hasKinks ? 0.22 : 0.14,
                    }}
                  />
                )}

                {points.map((point, index) => (
                  <Marker
                    key={point.id}
                    position={[point.lat, point.lng]}
                    icon={createVertexIcon(index + 1)}
                    interactive={false}
                  />
                ))}
              </MapContainer>

              {/* Canto superior direito: Botão expandir/fullscreen */}
              <button
                type="button"
                onClick={() => setIsMapExpanded((prev) => !prev)}
                aria-label={
                  isMapExpanded ? t("map.minimizeMap") : t("map.expandMap")
                }
                className="absolute top-3 right-3 z-[1000] flex h-10 w-10 items-center justify-center rounded-xl bg-white text-[#1F1C18] shadow-md transition-colors hover:bg-[#F7F6F0] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#511D4E]"
              >
                {isMapExpanded ? (
                  <Minimize2 className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Maximize2 className="h-4 w-4" aria-hidden="true" />
                )}
              </button>

              {/* Centro exato: Alfinete fixo via CSS */}
              <div
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 left-1/2 z-[1000] -translate-x-1/2 -translate-y-1/2"
              >
                <svg
                  width="34"
                  height="42"
                  viewBox="0 0 34 42"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="drop-shadow-[0_3px_6px_rgba(0,0,0,0.45)]"
                >
                  <path
                    d="M17 2C8.71573 2 2 8.71573 2 17C2 26.8 14.4 37.8 16.25 39.38C16.68 39.75 17.32 39.75 17.75 39.38C19.6 37.8 32 26.8 32 17C32 8.71573 25.2843 2 17 2Z"
                    fill="#511D4E"
                    stroke="#FFFFFF"
                    strokeWidth="2.5"
                  />
                  <circle cx="17" cy="17" r="4.5" fill="#FFFFFF" />
                </svg>
              </div>

              {/* Base centro: Tag branca flutuante */}
              <div className="pointer-events-none absolute bottom-5 left-1/2 z-[1000] -translate-x-1/2 rounded-xl bg-white px-4 py-2 text-xs font-medium whitespace-nowrap text-[#1F1C18] shadow-md">
                {t("map.moveMap")}
              </div>
            </div>
          </section>

          {/* Botões de Ação de Captura */}
          <section className="mt-4 space-y-2.5">
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={handleUseCurrentLocation}
              disabled={isLocating}
              className="w-full border-[#E6E4DA] bg-white text-[#511D4E] hover:bg-[#F7F6F0]"
            >
              <Crosshair
                className="h-4 w-4 text-[#511D4E]"
                aria-hidden="true"
              />
              {isLocating ? t("map.locatingGps") : t("map.useGps")}
            </Button>

            {gpsError && (
              <p className="text-xs font-medium text-[#C42311]">{gpsError}</p>
            )}

            <Button
              type="button"
              variant="primary"
              size="lg"
              onClick={handleMarkPinPoint}
              className="w-full"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              {t("map.markPin")}
            </Button>
          </section>

          {/* Lista de Pontos Adicionados */}
          <section className="mt-6">
            <div className="flex items-center justify-between">
              <h2 className="text-[15px] font-bold text-[#1F1C18]">
                {t("map.addedPoints")}
              </h2>
              <span className="text-[13px] font-medium text-[#6D6960]">
                {points.length}{" "}
                {points.length === 1
                  ? t("map.pointSingle")
                  : t("map.pointPlural")}
              </span>
            </div>

            {points.length > 0 ? (
              <ul className="mt-2.5 divide-y divide-[#E6E4DA]/70">
                {points.map((point, index) => (
                  <li
                    key={point.id}
                    className="flex items-center justify-between py-2 text-[13px] text-[#6D6960]"
                  >
                    <span>
                      {t("map.pointLabel", { index: index + 1 })}: Lat{" "}
                      {point.lat.toFixed(4)}, Lon {point.lng.toFixed(4)}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemovePoint(point.id)}
                      aria-label={t("map.removePoint", { index: index + 1 })}
                      className="flex h-7 w-7 items-center justify-center rounded-lg text-[#6D6960] transition-colors hover:bg-[#EFECE3] hover:text-[#1F1C18]"
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2.5 text-[13px] text-[#6D6960]">
                {t("map.emptyPoints")}
              </p>
            )}
          </section>

          {/* Alerta Condicional de Auto-Intersecção (@turf/kinks) */}
          {selfIntersection.hasKinks && (
            <Alert variant="warning" className="mt-5 border-[#C42311]/40 bg-[#C42311]/10">
              <AlertTriangle
                className="mt-0.5 h-5 w-5 shrink-0 text-[#C42311]"
                aria-hidden="true"
              />
              <div>
                <AlertTitle className="text-[15px] font-bold text-[#9B1C0E]">
                  Linhas da área se cruzando
                </AlertTitle>
                <AlertDescription className="mt-1 text-[13px] leading-relaxed text-[#9B1C0E]">
                  O contorno marcado possui {selfIntersection.kinkCoords.length}{" "}
                  {selfIntersection.kinkCoords.length === 1
                    ? "cruzamento de linha"
                    : "cruzamentos de linhas"}
                  . Remova e reposicione os pontos na ordem correta ao redor da
                  área para poder salvar.
                </AlertDescription>
              </div>
            </Alert>
          )}

          {/* Alerta Condicional de Área Excedida */}
          {isAreaTooLarge && !selfIntersection.hasKinks && (
            <Alert variant="warning" className="mt-5">
              <AlertTriangle
                className="mt-0.5 h-5 w-5 shrink-0 text-[#9A6B12]"
                aria-hidden="true"
              />
              <div>
                <AlertTitle className="text-[15px] font-bold text-[#7A520B]">
                  {t("map.largeAreaWarningTitle")}
                </AlertTitle>
                <AlertDescription className="mt-1 text-[13px] leading-relaxed text-[#7A520B]">
                  {t("map.largeAreaWarningDesc")}
                </AlertDescription>
              </div>
            </Alert>
          )}
        </div>

        <footer className="mt-8 flex flex-col items-center gap-3 pt-2">
          {saveError && (
            <p
              role="alert"
              className="w-full rounded-xl border border-[#C42311]/30 bg-[#C42311]/10 px-3 py-2 text-center text-xs font-medium text-[#C42311]"
            >
              {saveError}
            </p>
          )}

          <Button
            type="button"
            variant="primary"
            size="lg"
            disabled={!canSave || isSaving}
            onClick={() => void handleSave()}
            className="w-full"
          >
            {isSaving ? t("map.savingArea") : t("map.saveArea")}
          </Button>

          <Button
            type="button"
            variant="ghost"
            onClick={onBack}
            disabled={isSaving}
            className="w-full max-w-[200px] text-sm font-semibold text-[#511D4E]"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            <span>{t("common.back")}</span>
          </Button>
        </footer>
      </div>
    </div>
  );
}

