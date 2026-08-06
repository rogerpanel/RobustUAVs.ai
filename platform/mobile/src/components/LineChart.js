import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
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
}) {
  const { t } = useTheme();
  const s = styles(t);

  const pad = { l: 38, r: 12, t: 12, b: 30 };
  const w = Math.max(200, width);
  const h = Math.max(160, height);
  const iw = w - pad.l - pad.r;
  const ih = h - pad.t - pad.b;

  const xs = series.flatMap((ss) => ss.points.map((p) => p.x));
  const xMin = xs.length ? Math.min(...xs) : 0;
  const xMax = xs.length ? Math.max(...xs) : 1;

  const X = (x) => pad.l + (xMax === xMin ? 0 : (x - xMin) / (xMax - xMin)) * iw;
  const Y = (y) => pad.t + ih - ((y - yMin) / (yMax - yMin)) * ih;

  const linePath = (pts) =>
    pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(' ');

  const bandPath = (pts) => {
    if (!pts.length || pts[0].lo == null) return null;
    const up = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(p.x).toFixed(1)},${Y(p.hi).toFixed(1)}`);
    const dn = [...pts].reverse().map((p) => `L${X(p.x).toFixed(1)},${Y(p.lo).toFixed(1)}`);
    return `${up.join(' ')} ${dn.join(' ')} Z`;
  };

  const yTicks = [0, 0.25, 0.5, 0.75, 1.0].filter((v) => v >= yMin && v <= yMax);
  const xTickCount = iw < 260 ? 4 : 5;
  const xTicks = Array.from({ length: xTickCount }, (_, i) =>
    xMin + ((xMax - xMin) * i) / (xTickCount - 1));

  return (
    <View>
      <Svg width={w} height={h}>
        {yTicks.map((v) => (
          <React.Fragment key={`y${v}`}>
            <Line x1={pad.l} y1={Y(v)} x2={w - pad.r} y2={Y(v)}
                  stroke={t.border} strokeWidth={1} />
            <SvgText x={pad.l - 6} y={Y(v) + 3} fill={t.muted} fontSize="9"
                     textAnchor="end">{v.toFixed(2)}</SvgText>
          </React.Fragment>
        ))}
        {xTicks.map((v) => (
          <SvgText key={`x${v}`} x={X(v)} y={h - 10} fill={t.muted} fontSize="9"
                   textAnchor="middle">{Math.round(v)}</SvgText>
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

        {series.map((ss) => (
          <Path key={ss.key} d={linePath(ss.points)} stroke={ss.color}
                strokeWidth={2} fill="none" />
        ))}
        {series.map((ss) =>
          ss.points.map((p) => (
            <Circle key={`${ss.key}-${p.x}`} cx={X(p.x)} cy={Y(p.y)} r={2}
                    fill={ss.color} />
          )))}
      </Svg>

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
});
