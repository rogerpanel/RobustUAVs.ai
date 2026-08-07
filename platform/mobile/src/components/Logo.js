import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Path, Circle, G, Rect } from 'react-native-svg';
import { useTheme, fonts } from '../theme';

/**
 * The RobustUAVs.ai mark, in the app.
 *
 * Same geometry as public/favicon.svg, redrawn as a component so the rail, the
 * cover page and the browser tab all carry one identity. Built from the
 * hand-drawn sketch: stacked strokes converging from both sides, which is the
 * paper's thesis rather than a picture of a drone -- network flowing one way,
 * autonomy the other, meeting at a single interface.
 *
 * `chrome=false` drops the rounded plate so the mark can sit on the panel
 * background without a second surface behind it.
 */
export default function Logo({ size = 28, chrome = true }) {
  const { t } = useTheme();
  const k = size / 64;
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64">
      {chrome ? <Rect width={64} height={64} rx={13} fill={t.bgPrimary} /> : null}
      <G strokeLinecap="round" strokeLinejoin="round" fill="none" strokeWidth={3.2}>
        <G stroke={t.network}>
          <Path d="M7 18 H23" /><Path d="M5 27 H26" />
          <Path d="M8 36 H23" /><Path d="M11 45 H20" />
          <Path d="M20.5 24.5 L26.5 27 L20.5 29.5" />
          <Path d="M17.5 33.5 L23.5 36 L17.5 38.5" />
        </G>
        <G stroke={t.autonomy}>
          <Path d="M57 18 H41" /><Path d="M59 27 H38" />
          <Path d="M56 36 H41" /><Path d="M53 45 H44" />
          <Path d="M43.5 24.5 L37.5 27 L43.5 29.5" />
          <Path d="M46.5 33.5 L40.5 36 L46.5 38.5" />
        </G>
        <Path d="M32 20 L32 44" stroke={t.accent} strokeWidth={3.4} />
      </G>
      <Circle cx={32} cy={31.5} r={4.6} fill={t.accent} />
      <Circle cx={32} cy={31.5} r={1.9} fill={t.bgPrimary} />
    </Svg>
  );
}

/** Mark plus wordmark, for the rail header and the cover. */
export function Wordmark({ size = 22, subtitle }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View style={s.row}>
      <Logo size={size * 1.25} chrome={false} />
      <View style={s.text}>
        <Text style={[s.mark, { fontSize: size }]} numberOfLines={1}>
          RobustUAVs<Text style={{ color: t.accent }}>.ai</Text>
        </Text>
        {subtitle ? <Text style={s.sub}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },
  text: { marginLeft: 7, flexShrink: 1 },
  mark: {
    color: t.text, fontWeight: '800', letterSpacing: -0.4,
    fontFamily: fonts.display,
  },
  sub: {
    color: t.muted, fontSize: 8, fontWeight: '700', letterSpacing: 1,
    textTransform: 'uppercase', marginTop: 2,
  },
});
