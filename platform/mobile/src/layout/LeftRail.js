import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useTheme, fonts } from '../theme';
import { LEFT_GROUPS } from './nav';
import Rail from './Rail';

/**
 * Primary navigation. Pinned on wide and medium screens, and the body of the
 * overlay drawer on phones -- one component either way, so the two can never
 * present a different set of routes.
 *
 * `compact` widens the rows to a thumb-sized target and shows the one-line
 * blurb, which fits in a full-height drawer and not in a 196 px rail.
 */
export default function LeftRail({ route, onNavigate, compact = false, onDismiss }) {
  const { t, mode, toggle } = useTheme();
  const s = styles(t, compact);

  const header = (
    <View style={s.brand}>
      <Text style={s.wordmark} numberOfLines={1}>
        RobustUAVs<Text style={{ color: t.accent }}>.ai</Text>
      </Text>
      <Text style={s.eyebrow}>NDSS 2027 · artifact</Text>
    </View>
  );

  const footer = (
    <Pressable onPress={toggle} style={s.themeBtn} accessibilityRole="button">
      <Text style={s.themeText} numberOfLines={1}>
        {mode === 'dark' ? '☀  print theme' : '☾  dark theme'}
      </Text>
    </Pressable>
  );

  return (
    <Rail side="left" compact={compact} header={header} footer={footer}>
      {LEFT_GROUPS.map((g) => (
        <View key={g.label} style={s.group}>
          <Text style={s.groupLabel} numberOfLines={1}>{g.label}</Text>
          {g.items.map((it) => {
            const on = it.key === route;
            return (
              <Pressable
                key={it.key}
                onPress={() => { onNavigate(it.key); onDismiss?.(); }}
                style={[s.row, on && s.rowOn]}
                accessibilityRole="button"
                accessibilityState={{ selected: on }}
                accessibilityLabel={it.title}
              >
                <Text style={[s.glyph, on && { color: t.accent }]}>{it.glyph}</Text>
                <View style={s.rowText}>
                  <Text style={[s.title, on && s.titleOn]}>{it.title}</Text>
                  {compact ? <Text style={s.blurb}>{it.blurb}</Text> : null}
                </View>
                {/* A page whose figures are illustrative rather than read from
                    a committed result is marked here, so the distinction is
                    visible before you open it rather than only on the page. */}
                {it.grounded === false ? <View style={s.illus} /> : null}
              </Pressable>
            );
          })}
        </View>
      ))}
    </Rail>
  );
}

const styles = (t, compact) => StyleSheet.create({
  brand: {
    paddingHorizontal: 9, paddingTop: 12, paddingBottom: 9,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  wordmark: {
    color: t.text, fontSize: compact ? 20 : 14, fontWeight: '800',
    letterSpacing: -0.4, fontFamily: fonts.display,
  },
  eyebrow: {
    color: t.muted, fontSize: 8, fontWeight: '700', letterSpacing: 1,
    textTransform: 'uppercase', marginTop: 3,
  },
  group: { marginBottom: 12 },
  groupLabel: {
    color: t.muted, fontSize: 8, fontWeight: '800', letterSpacing: 0.9,
    textTransform: 'uppercase', paddingHorizontal: 9, marginBottom: 3,
  },
  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 9, paddingVertical: compact ? 10 : 5,
    minHeight: compact ? 46 : 26,
    borderLeftWidth: 2, borderLeftColor: 'transparent',
  },
  rowOn: { backgroundColor: `${t.accent}1A`, borderLeftColor: t.accent },
  glyph: { color: t.muted, fontSize: 11, width: 16 },
  rowText: { flexShrink: 0, paddingRight: 8 },
  title: { color: t.muted, fontSize: compact ? 13.5 : 11, fontWeight: '600' },
  titleOn: { color: t.text, fontWeight: '700' },
  blurb: { color: t.muted, fontSize: 10, marginTop: 1 },
  illus: {
    width: 5, height: 5, borderRadius: 2.5,
    backgroundColor: t.bridge, marginLeft: 2,
  },
  themeBtn: {
    borderTopWidth: 1, borderTopColor: t.border,
    paddingVertical: 9, alignItems: 'center',
  },
  themeText: { color: t.muted, fontSize: 9.5, fontWeight: '600' },
});
