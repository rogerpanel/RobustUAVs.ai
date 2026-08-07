import React, { useState } from 'react';
import { View, Text, Pressable, StyleSheet, Modal, Platform } from 'react-native';
import { useTheme, fonts } from '../theme';

/**
 * Export whatever the page is currently showing.
 *
 * Four formats, chosen because each is producible without a dependency:
 *
 *   JSON  the exact payload the API returned, so a reader can re-derive
 *         everything on the page rather than trusting the rendering
 *   CSV   the tabular view, when the page has one
 *   PNG   the page's chart, by serialising its SVG through a canvas. Only
 *         offered when the page passes an `svgId`
 *   PDF   the browser's own print pipeline
 *
 * Deliberately no html2canvas or jsPDF. Both are large, both have historically
 * broken Expo web exports, and the browser already does PDF properly. A print
 * stylesheet gives a cleaner result than a rasterised screenshot anyway.
 *
 * Every export carries a provenance header naming the deployment, the UTC time
 * and the source files -- an exported figure that turns up in a slide deck six
 * months later should still say where it came from.
 */
export default function ExportMenu({ title, data, csv, svgId, sources }) {
  const { t } = useTheme();
  const s = styles(t);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState(null);

  const stamp = () => {
    try { return new Date().toISOString(); } catch { return 'unknown'; }
  };
  const slug = (title || 'export').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const provenance = {
    exported_from: 'RobustUAVs.ai',
    page: title,
    exported_at_utc: stamp(),
    origin: typeof window !== 'undefined' ? window.location?.origin : null,
    sources: sources ?? null,
    note: 'Figures marked illustrative on the page are illustrative here too.',
  };

  const download = (blob, filename) => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') {
      setNote('Export is available in the browser build.');
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    // Revoke on the next tick: revoking synchronously races the download in
    // Safari and produces a zero-byte file.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNote(`saved ${filename}`);
  };

  const asJson = () => {
    const body = JSON.stringify({ provenance, data }, null, 2);
    download(new Blob([body], { type: 'application/json' }), `${slug}-${Date.now()}.json`);
  };

  const asCsv = () => {
    if (!csv || !csv.length) { setNote('This page has no tabular view.'); return; }
    const cols = Object.keys(csv[0]);
    const esc = (v) => {
      const str = v == null ? '' : String(v);
      return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
    };
    const lines = [
      `# RobustUAVs.ai — ${title}`,
      `# exported ${provenance.exported_at_utc}`,
      ...(sources ? [`# source: ${sources}`] : []),
      cols.join(','),
      ...csv.map((r) => cols.map((c) => esc(r[c])).join(',')),
    ];
    download(new Blob([lines.join('\n')], { type: 'text/csv' }), `${slug}-${Date.now()}.csv`);
  };

  const asPng = () => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') {
      setNote('PNG export is available in the browser build.'); return;
    }
    const el = svgId ? document.getElementById(svgId) : null;
    const svg = el?.tagName?.toLowerCase() === 'svg' ? el : el?.querySelector('svg');
    if (!svg) { setNote('No chart on this page to export.'); return; }
    const rect = svg.getBoundingClientRect();
    const w = Math.max(1, Math.round(rect.width)) * 2;   // 2x for a usable slide
    const h = Math.max(1, Math.round(rect.height)) * 2;
    const xml = new XMLSerializer().serializeToString(svg);
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      const ctx = c.getContext('2d');
      // The SVG has no background of its own; without this the PNG is
      // transparent and unreadable on a white slide.
      ctx.fillStyle = t.bg; ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      c.toBlob((blob) => blob && download(blob, `${slug}-${Date.now()}.png`));
    };
    img.onerror = () => setNote('Could not rasterise the chart.');
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;
  };

  const asPdf = () => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') {
      setNote('PDF export is available in the browser build.'); return;
    }
    setOpen(false);
    // The print theme exists for exactly this: the dark palette prints as a
    // sheet of ink and washes out every status colour.
    setTimeout(() => window.print(), 150);
  };

  const items = [
    { id: 'json', label: 'JSON', note: 'the exact API payload', run: asJson },
    ...(csv?.length ? [{ id: 'csv', label: 'CSV', note: 'the table on this page', run: asCsv }] : []),
    ...(svgId ? [{ id: 'png', label: 'PNG', note: 'the chart, at 2× for slides', run: asPng }] : []),
    { id: 'pdf', label: 'PDF', note: 'via the browser — switch to the print theme first', run: asPdf },
  ];

  return (
    <>
      <Pressable onPress={() => { setOpen(true); setNote(null); }} style={s.trigger}
                 accessibilityRole="button" accessibilityLabel="Export this page">
        <Text style={s.triggerText}>⤓  export</Text>
      </Pressable>

      <Modal visible={open} transparent animationType="fade"
             onRequestClose={() => setOpen(false)}>
        <Pressable style={s.scrim} onPress={() => setOpen(false)} />
        <View style={s.sheet}>
          <Text style={s.title}>Export · {title}</Text>
          <Text style={s.body}>
            Each file carries a provenance header: this deployment, the UTC time,
            and the source files behind the numbers.
          </Text>
          {items.map((it) => (
            <Pressable key={it.id} onPress={it.run} style={s.row}>
              <Text style={s.fmt}>{it.label}</Text>
              <Text style={s.fmtNote}>{it.note}</Text>
            </Pressable>
          ))}
          {note ? <Text style={s.status}>{note}</Text> : null}
          <Pressable onPress={() => setOpen(false)} style={s.close}>
            <Text style={s.closeText}>close</Text>
          </Pressable>
        </View>
      </Modal>
    </>
  );
}

const styles = (t) => StyleSheet.create({
  trigger: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 10, paddingVertical: 6,
  },
  triggerText: { color: t.muted, fontSize: 10.5, fontWeight: '700' },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: '#00000099' },
  sheet: {
    position: 'absolute', top: 70, right: 16, width: 300, maxWidth: '90%',
    backgroundColor: t.panel, borderWidth: 1, borderColor: t.border,
    borderRadius: 11, padding: 14,
  },
  title: { color: t.text, fontSize: 13.5, fontWeight: '800', fontFamily: fonts.display },
  body: { color: t.muted, fontSize: 10.5, lineHeight: 15.5, marginTop: 4, marginBottom: 9 },
  row: {
    borderWidth: 1, borderColor: t.border, borderRadius: 8,
    paddingVertical: 9, paddingHorizontal: 11, marginBottom: 6,
  },
  fmt: { color: t.accent, fontSize: 12.5, fontWeight: '800' },
  fmtNote: { color: t.muted, fontSize: 10, marginTop: 1 },
  status: { color: t.ok, fontSize: 10.5, marginTop: 4 },
  close: { alignSelf: 'flex-end', paddingVertical: 6, paddingHorizontal: 4 },
  closeText: { color: t.muted, fontSize: 10.5, fontWeight: '700' },
});
