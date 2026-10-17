import React, { useCallback, useState } from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import Svg, { Path, Line, Circle, Text as SvgText, Rect } from 'react-native-svg';
import { useTheme, fonts } from '../theme';

/**
 * A small multi-series line chart with an optional threshold rule.
 *
 * Deliberately not a charting library: the only chart this app draws is
 * MCR-vs-J/S, and a dependency that renders a hundred chart types would cost
 * more bundle -- and more build memory on a host that has already run out of it
 * once -- than the fifty lines it would replace.
 *
 * Confidence intervals are drawn as a band rather than as error bars. At 33
 * grid points error bars turn into a picket fence; a band reads as one object
 * and still shows where the intervals widen.
 */
export default function LineChart({
  series = [],            // [{ key, label, color, points: [{x, y, lo, hi}] }]
  width = 320,
  height = 220,
  xLabel = '',
  yLabel = '',
  yMin = 0,
  yMax = 1.05,
  threshold = null,       // { y, label, color }
  marker = null,          // { x, label } — the operating point
  xUnit = '',
  yUnit = '',
  onHover = null,
  overlay = [],           // [{ x, y, label, color }] -- reference points, drawn as rings
  vlines = [],            // [{ x, label, color }] -- e.g. where a verdict flips
}) {
  const { t } = useTheme();
  const s = styles(t);
  // Crosshair state. Pointer events only exist on web; on native the chart
  // stays static rather than pretending to support a hover it cannot receive.
  const [cursor, setCursor] = useState(null);

  const pad = { l: 38, r: 12, t: 12, b: 30 };
  const w = Math.max(200, width);
  const h = Math.max(160, height);
  const iw = w - pad.l - pad.r;
  const ih = h - pad.t - pad.b;

  const xs = [...series.flatMap((ss) => ss.points.map((p) => p.x)),
              ...overlay.map((p) => p.x)].filter(Number.isFinite);
  const xMin = xs.length ? Math.min(...xs) : 0;
  const xMax = xs.length ? Math.max(...xs) : 1;

  const X = (x) => pad.l + (xMax === xMin ? 0 : (x - xMin) / (xMax - xMin)) * iw;
  const Y = (y) => pad.t + ih - ((y - yMin) / (yMax - yMin)) * ih;

  // Nearest sample on the x axis, then every series' value there. Snapping to
  // a measured x rather than interpolating means the readout never shows a
  // number that was not run -- the same rule the J/S selector follows.
  const handleMove = useCallback((evt) => {
    if (Platform.OS !== 'web') return;
    const box = evt.currentTarget?.getBoundingClientRect?.();
    if (!box) return;
    const px = evt.clientX - box.left;
    if (px < pad.l - 6 || px > w - pad.r + 6) { setCursor(null); onHover?.(null); return; }
    const xv = xMin + ((px - pad.l) / iw) * (xMax - xMin);
    const xs2 = [...new Set(series.flatMap((ss) => ss.points.map((p) => p.x)))];
    if (!xs2.length) return;
    const nearest = xs2.reduce((a, b) => (Math.abs(b - xv) < Math.abs(a - xv) ? b : a));
    const readout = {
      x: nearest,
      values: series.map((ss) => {
        const pt = ss.points.find((p) => p.x === nearest);
        return pt ? { key: ss.key, label: ss.label, color: ss.color, y: pt.y,
                      lo: pt.lo, hi: pt.hi } : null;
      }).filter(Boolean),
    };
    setCursor(readout);
    onHover?.(readout);
  }, [series, xMin, xMax, iw, w, pad.l, pad.r, onHover]);

  const handleLeave = useCallback(() => { setCursor(null); onHover?.(null); }, [onHover]);

  // Non-finite values (an infeasible scheme's inf) break the line rather than
  // being drawn at an invented height.
  const ok = (p) => Number.isFinite(p.x) && Number.isFinite(p.y);
  const clampY = (y) => Math.max(yMin, Math.min(yMax, y));
  const linePath = (pts) => {
    let pen = 'M';
    return pts.map((p) => {
      if (!ok(p)) { pen = 'M'; return ''; }
      const seg = `${pen}${X(p.x).toFixed(1)},${Y(clampY(p.y)).toFixed(1)}`;
      pen = 'L';
      return seg;
    }).join(' ');
  };

  const bandPath = (pts) => {
    if (!pts.length || pts[0].lo == null) return null;
    const up = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(p.x).toFixed(1)},${Y(p.hi).toFixed(1)}`);
    const dn = [...pts].reverse().map((p) => `L${X(p.x).toFixed(1)},${Y(p.lo).toFixed(1)}`);
    return `${up.join(' ')} ${dn.join(' ')} Z`;
  };

  // Probability axes keep their quarter ticks; anything else gets round
  // numbers spanning the actual range, so a value above 1 has a tick to read.
  const yTicks = (yMin >= 0 && yMax <= 1.05 && yMax - yMin > 0.5)
    ? [0, 0.25, 0.5, 0.75, 1.0].filter((v) => v >= yMin && v <= yMax)
    : niceTicks(yMin, yMax, 5);
  const xTicks = niceTicks(xMin, xMax, iw < 260 ? 4 : 6);

  const hoverProps = Platform.OS === 'web'
    ? { onMouseMove: handleMove, onMouseLeave: handleLeave }
    : {};

  return (
    <View>
      <View {...hoverProps} style={{ cursor: 'crosshair' }}>
      <Svg width={w} height={h}>
        {yTicks.map((v) => (
          <React.Fragment key={`y${v}`}>
            <Line x1={pad.l} y1={Y(v)} x2={w - pad.r} y2={Y(v)}
                  stroke={t.border} strokeWidth={1} />
            <SvgText x={pad.l - 6} y={Y(v) + 3} fill={t.muted} fontSize="9"
                     textAnchor="end">{tickLabel(v)}</SvgText>
          </React.Fragment>
        ))}
        {xTicks.map((v) => (
          <SvgText key={`x${v}`} x={X(v)} y={h - 10} fill={t.muted} fontSize="9"
                   textAnchor="middle">{tickLabel(v)}</SvgText>
        ))}

        {series.map((ss) => {
          const bp = bandPath(ss.points);
          return bp ? (
            <Path key={`b${ss.key}`} d={bp} fill={ss.color} opacity={0.13} />
          ) : null;
        })}

        {threshold != null ? (
          <>
            <Line x1={pad.l} y1={Y(threshold.y)} x2={w - pad.r} y2={Y(threshold.y)}
                  stroke={threshold.color ?? t.bridge} strokeWidth={1.5}
                  strokeDasharray="5,4" />
            <SvgText x={w - pad.r - 2} y={Y(threshold.y) - 4}
                     fill={threshold.color ?? t.bridge} fontSize="9" textAnchor="end">
              {threshold.label}
            </SvgText>
          </>
        ) : null}

        {marker != null ? (
          <>
            <Rect x={X(marker.x) - 0.75} y={pad.t} width={1.5} height={ih}
                  fill={t.accent} opacity={0.55} />
            <SvgText x={X(marker.x)} y={pad.t - 2} fill={t.accent} fontSize="9"
                     textAnchor="middle">{marker.label}</SvgText>
          </>
        ) : null}

        {vlines.map((v, i) => (
          <React.Fragment key={`v${i}`}>
            <Line x1={X(v.x)} y1={pad.t} x2={X(v.x)} y2={pad.t + ih}
                  stroke={v.color ?? t.danger} strokeWidth={1.2} strokeDasharray="3,3" />
            <SvgText x={X(v.x) + 3} y={pad.t + 10 + 11 * i} fill={v.color ?? t.danger}
                     fontSize="9">{v.label}</SvgText>
          </React.Fragment>
        ))}

        {series.map((ss) => (
          <Path key={ss.key} d={linePath(ss.points)} stroke={ss.color}
                strokeWidth={2} fill="none"
                strokeDasharray={ss.dash ? '5,4' : undefined} />
        ))}
        {series.map((ss) =>
          ss.points.filter(ok).map((p) => (
            <Circle key={`${ss.key}-${p.x}`} cx={X(p.x)} cy={Y(clampY(p.y))} r={2}
                    fill={ss.color} />
          )))}
        {overlay.filter(ok).map((p, i) => (
          <Circle key={`o${i}`} cx={X(p.x)} cy={Y(clampY(p.y))} r={5}
                  fill="none" stroke={p.color ?? t.text} strokeWidth={1.8} />
        ))}

        {/* Crosshair. Drawn last so it sits above every series. */}
        {cursor ? (
          <>
            <Line x1={X(cursor.x)} y1={pad.t} x2={X(cursor.x)} y2={pad.t + ih}
                  stroke={t.text} strokeWidth={1} opacity={0.45} />
            {cursor.values.map((v) => (
              <Circle key={`c${v.key}`} cx={X(cursor.x)} cy={Y(v.y)} r={4.5}
                      fill={v.color} stroke={t.bg} strokeWidth={1.5} />
            ))}
          </>
        ) : null}
      </Svg>
      </View>

      {/* Readout below rather than a floating tooltip: a tooltip that follows
          the cursor covers the very curve it describes, and reflows the layout
          on every mouse move. A fixed block does neither. */}
      {cursor ? (
        <View style={s.readout}>
          <Text style={s.readoutX}>
            {xLabel || 'x'} = {cursor.x}{xUnit}
          </Text>
          <View style={s.readoutRow}>
            {cursor.values.map((v) => (
              <View key={`r${v.key}`} style={s.readoutItem}>
                <View style={[s.swatch, { backgroundColor: v.color }]} />
                <Text style={s.readoutLabel} numberOfLines={1}>{v.label}</Text>
                <Text style={[s.readoutValue, { color: v.color }]}>
                  {typeof v.y === 'number' ? v.y.toFixed(3) : v.y}{yUnit}
                </Text>
                {v.lo != null ? (
                  <Text style={s.readoutCi}>
                    [{v.lo.toFixed(3)}, {v.hi.toFixed(3)}]
                  </Text>
                ) : null}
              </View>
            ))}
          </View>
        </View>
      ) : (
        <Text style={s.hoverHint}>
          {Platform.OS === 'web' ? 'Move the pointer across the chart to read values.' : ''}
        </Text>
      )}

      <View style={s.axes}>
        <Text style={s.axis}>{yLabel}</Text>
        <Text style={s.axis}>{xLabel}</Text>
      </View>
      <View style={s.legend}>
        {series.map((ss) => (
          <View key={`l${ss.key}`} style={s.legendItem}>
            <View style={[s.swatch, { backgroundColor: ss.color }]} />
            <Text style={s.legendText}>{ss.label}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  axes: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 2 },
  axis: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono },
  legend: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  legendItem: { flexDirection: 'row', alignItems: 'center', marginRight: 12, marginBottom: 4 },
  swatch: { width: 10, height: 3, borderRadius: 2, marginRight: 5 },
  legendText: { color: t.muted, fontSize: 10.5 },
  readout: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    backgroundColor: t.bg, padding: 8, marginTop: 6,
  },
  readoutX: {
    color: t.accent, fontSize: 11, fontWeight: '800',
    fontFamily: fonts.mono, marginBottom: 4,
  },
  readoutRow: { flexDirection: 'row', flexWrap: 'wrap' },
  readoutItem: {
    flexDirection: 'row', alignItems: 'center',
    marginRight: 14, marginBottom: 3,
  },
  readoutLabel: { color: t.muted, fontSize: 10.5, marginRight: 5 },
  readoutValue: { fontSize: 11, fontWeight: '800', fontFamily: fonts.mono },
  readoutCi: { color: t.muted, fontSize: 9, fontFamily: fonts.mono, marginLeft: 4 },
  hoverHint: { color: t.muted, fontSize: 9.5, marginTop: 6, fontStyle: 'italic' },
});

/** Round-number ticks covering [lo, hi]. */
function niceTicks(lo, hi, count) {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [];
  if (hi === lo) return [lo];
  const raw = (hi - lo) / Math.max(1, count - 1);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9 * step; v += step) {
    out.push(Number(v.toPrecision(12)));
  }
  return out;
}

function tickLabel(v) {
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (a >= 1e6) return v.toExponential(0);
  if (Number.isInteger(v)) return String(v);
  return String(Number(v.toPrecision(3)));
}
