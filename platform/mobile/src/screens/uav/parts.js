import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme, fonts } from '../../theme';
import ExportMenu from '../../components/ExportMenu';

/**
 * The chrome every page in this group shares.
 *
 * `ScreenHeader`'s `grounded` flag is the load-bearing one: it renders a badge
 * saying whether the figures below were read from a committed result or are
 * illustrative. Every page in the group sets it, so a viewer never has to guess
 * which kind of number they are looking at, and a page cannot quietly present
 * a simulator output as a measurement.
 */

export function ScreenHeader({ eyebrow, title, lede, grounded, source,
                               exportData, exportCsv, exportSvgId }) {
  const { t } = useTheme();
  const s = styles(t);
  const exportable = exportData != null || exportCsv != null || exportSvgId != null;
  return (
    <View style={s.header}>
      <View style={s.titleRow}>
        <View style={{ flex: 1 }}>
          <Text style={s.eyebrow}>{eyebrow}</Text>
          <Text style={s.h1}>{title}</Text>
        </View>
        {exportable ? (
          <ExportMenu title={title} data={exportData} csv={exportCsv}
                      svgId={exportSvgId} sources={source} />
        ) : null}
      </View>
      {lede ? <Text style={s.lede}>{lede}</Text> : null}
      <View style={s.badges}>
        <View style={[s.badge, { borderColor: grounded ? t.ok : t.bridge }]}>
          <Text style={[s.badgeText, { color: grounded ? t.ok : t.bridge }]}>
            {grounded ? 'measured' : 'illustrative'}
          </Text>
        </View>
        {source ? <Text style={s.source}>{source}</Text> : null}
      </View>
    </View>
  );
}

export function Panel({ title, subtitle, accent, children }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View style={[s.panel, accent ? { borderTopColor: accent, borderTopWidth: 3 } : null]}>
      {title ? <Text style={s.panelTitle}>{title}</Text> : null}
      {subtitle ? <Text style={s.panelSub}>{subtitle}</Text> : null}
      <View style={title || subtitle ? { marginTop: 10 } : null}>{children}</View>
    </View>
  );
}

export function KV({ k, v, tone }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View style={s.kv}>
      <Text style={s.k}>{k}</Text>
      <Text style={[s.v, tone ? { color: tone } : null]}>{String(v)}</Text>
    </View>
  );
}

export function Tag({ label, color }) {
  const { t } = useTheme();
  const s = styles(t);
  const c = color ?? t.muted;
  return (
    <View style={[s.tag, { borderColor: c }]}>
      <Text style={[s.tagText, { color: c }]}>{label}</Text>
    </View>
  );
}

/**
 * A 503 from this API means "this result has not been produced in this
 * deployment", not "something broke". Saying "failed" would misreport a
 * data-gated item as a bug, so the wording is deliberate.
 */
export function Unavailable({ message }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View style={s.unavail}>
      <Text style={s.unavailTitle}>Not produced in this deployment</Text>
      <Text style={s.unavailBody}>{message}</Text>
      <Text style={s.unavailHint}>
        Data-gated items are listed in PENDING_ON_DATA.md. This is a missing
        input, not a failure.
      </Text>
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  header: { marginBottom: 14 },
  titleRow: { flexDirection: 'row', alignItems: 'flex-start' },
  eyebrow: {
    color: t.accent, fontSize: 9.5, fontWeight: '800', letterSpacing: 1.3,
    textTransform: 'uppercase', marginBottom: 5,
  },
  h1: {
    color: t.text, fontSize: 23, fontWeight: '800', letterSpacing: -0.5,
    fontFamily: fonts.display,
  },
  lede: { color: t.muted, fontSize: 12.5, lineHeight: 19, marginTop: 7 },
  badges: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', marginTop: 9 },
  badge: {
    borderWidth: 1, borderRadius: 5, paddingHorizontal: 6, paddingVertical: 2,
    marginRight: 8, marginBottom: 4,
  },
  badgeText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase' },
  source: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, marginBottom: 4 },

  panel: {
    backgroundColor: t.panel, borderWidth: 1, borderColor: t.border,
    borderRadius: 10, padding: 14, marginBottom: 12,
  },
  panelTitle: { color: t.text, fontSize: 14, fontWeight: '700', fontFamily: fonts.display },
  panelSub: { color: t.muted, fontSize: 10.5, lineHeight: 15.5, marginTop: 3 },

  kv: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: t.border,
  },
  k: { color: t.muted, fontSize: 11.5, flex: 1, paddingRight: 8 },
  v: { color: t.text, fontSize: 11.5, fontWeight: '700', textAlign: 'right' },

  tag: {
    borderWidth: 1, borderRadius: 5, paddingHorizontal: 6, paddingVertical: 2,
    marginRight: 5, marginBottom: 5,
  },
  tagText: { fontSize: 9.5, fontWeight: '700' },

  unavail: { margin: 16, borderLeftWidth: 3, borderLeftColor: t.bridge, paddingLeft: 12 },
  unavailTitle: { color: t.bridge, fontSize: 13, fontWeight: '800' },
  unavailBody: { color: t.text, fontSize: 12, lineHeight: 18, marginTop: 5 },
  unavailHint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 8 },
});
