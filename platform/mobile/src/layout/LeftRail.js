import React from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet } from 'react-native';
import { useTheme, fonts } from '../theme';
import { LEFT_GROUPS } from './nav';
import { LEFT_RAIL_W } from './useLayout';

/**
 * Primary navigation. Rendered pinned on wide and medium screens, and as the
 * body of the overlay drawer on phones -- same component either way, so the
 * two can never present a different set of routes.
 *
 * `compact` widens the rows to a thumb-sized target and shows the one-line
 * blurb, which there is room for in a full-height drawer and not in a 232 px
 * rail sitting beside content.
 */
export default function LeftRail({ route, onNavigate, compact = false, onDismiss }) {
  const { t, mode, toggle } = useTheme();
  const s = styles(t, compact);

  return (
    <View style={s.rail}>
      <View style={s.brand}>
        <Text style={s.wordmark}>
          RobustUAVs<Text style={{ color: t.accent }}>.ai</Text>
        </Text>
        <Text style={s.eyebrow}>NDSS 2027 · artifact</Text>
      </View>

      <ScrollView style={s.scroll} contentContainerStyle={s.scrollBody}>
        {LEFT_GROUPS.map((g) => (
          <View key={g.label} style={s.group}>
            <Text style={s.groupLabel}>{g.label}</Text>
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
                  <Text style={[s.glyph, on && s.glyphOn]}>{it.glyph}</Text>
                  <View style={s.rowText}>
                    <Text style={[s.title, on && s.titleOn]} numberOfLines={1}>
                      {it.title}
                    </Text>
                    {compact ? (
                      <Text style={s.blurb} numberOfLines={1}>{it.blurb}</Text>
                    ) : null}
                  </View>
                </Pressable>
              );
            })}
          </View>
        ))}
      </ScrollView>

      {/* Theme switch lives at the foot of the rail because it is a presenter
          control, not a route -- and on the day it is the first thing touched. */}
      <Pressable onPress={toggle} style={s.themeBtn} accessibilityRole="button">
        <Text style={s.themeText}>
          {mode === 'dark' ? '☀  print theme' : '☾  dark theme'}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = (t, compact) => StyleSheet.create({
  rail: {
    width: compact ? '100%' : LEFT_RAIL_W,
    flex: 1,
    backgroundColor: t.panel,
    borderRightWidth: compact ? 0 : 1,
    borderRightColor: t.border,
  },
  brand: {
    paddingHorizontal: 14, paddingTop: 16, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  wordmark: {
    color: t.text, fontSize: compact ? 21 : 18, fontWeight: '800',
    letterSpacing: -0.5, fontFamily: fonts.display,
  },
  eyebrow: {
    color: t.muted, fontSize: 9, fontWeight: '700', letterSpacing: 1.2,
    textTransform: 'uppercase', marginTop: 3,
  },
  scroll: { flex: 1 },
  scrollBody: { paddingVertical: 10 },
  group: { marginBottom: 14 },
  groupLabel: {
    color: t.muted, fontSize: 9, fontWeight: '800', letterSpacing: 1.1,
    textTransform: 'uppercase', paddingHorizontal: 14, marginBottom: 5,
  },
  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 14, paddingVertical: compact ? 11 : 7,
    minHeight: compact ? 46 : 32,
    borderLeftWidth: 2, borderLeftColor: 'transparent',
  },
  rowOn: { backgroundColor: `${t.accent}1A`, borderLeftColor: t.accent },
  glyph: { color: t.muted, fontSize: 13, width: 22 },
  glyphOn: { color: t.accent },
  rowText: { flex: 1 },
  title: { color: t.muted, fontSize: compact ? 14 : 12.5, fontWeight: '600' },
  titleOn: { color: t.text, fontWeight: '700' },
  blurb: { color: t.muted, fontSize: 10.5, marginTop: 1 },
  themeBtn: {
    borderTopWidth: 1, borderTopColor: t.border,
    paddingVertical: 12, alignItems: 'center',
  },
  themeText: { color: t.muted, fontSize: 11, fontWeight: '600' },
});
