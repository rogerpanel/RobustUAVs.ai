import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useTheme, fonts } from '../../theme';
import { fmt, Pills, Field, Button } from './parts';

/**
 * Building blocks for the "show the working" panels on the paper pages.
 *
 * A calculator that only prints its verdict asks to be trusted. These panels
 * show the computation instead: the inequality written out with the values it
 * used, the same computation swept across an input, and the steps of a
 * process replayed one at a time. Every number shown comes from the server,
 * which calls the paper's own code; nothing here computes a result.
 */

/** The computation written out, one line per step, with the value it produced. */
export function Steps({ steps }) {
  const { t } = useTheme();
  const s = styles(t);
  if (!steps?.length) return null;
  return (
    <View>
      {steps.map((st, i) => (
        <View key={st.step} style={s.step}>
          <View style={s.stepNo}><Text style={s.stepNoText}>{i + 1}</Text></View>
          <View style={{ flex: 1 }}>
            <Text style={s.stepTitle}>{st.step}</Text>
            {st.expr ? <Text style={s.stepExpr}>{st.expr}</Text> : null}
          </View>
          <Text style={s.stepVal}>{fmt(st.value)}{st.unit ? ` ${st.unit}` : ''}</Text>
        </View>
      ))}
    </View>
  );
}

/** Pick an input, a range and a resolution; the caller runs the sweep. */
export function SweepControls({ options, vary, onVary, lo, hi, onLo, onHi, n, onN,
                                onRun, busy, label = 'sweep' }) {
  const { t } = useTheme();
  const s = styles(t);
  return (
    <View>
      <Text style={s.label}>input to vary</Text>
      <Pills options={Object.keys(options)} value={vary} onChange={onVary}
             labelOf={(k) => options[k]} />
      <View style={s.row}>
        <View style={s.cell}><Field label="from" value={lo} onChange={onLo} /></View>
        <View style={s.cell}><Field label="to" value={hi} onChange={onHi} /></View>
        {onN ? <View style={s.cell}><Field label="points" value={n} onChange={onN} /></View> : null}
      </View>
      <Button label={label} onPress={onRun} busy={busy} busyLabel="running…" />
    </View>
  );
}

/**
 * Step through a sequence (0..max) by hand or let it play. Playing stops at
 * the end rather than looping, so the last frame -- usually the point of the
 * demonstration -- stays on screen.
 */
export function Player({ max, value, onChange, label = 'step', interval = 900 }) {
  const { t } = useTheme();
  const s = styles(t);
  const [playing, setPlaying] = useState(false);
  const ref = useRef(value);
  ref.current = value;
  useEffect(() => {
    if (!playing) return undefined;
    const id = setInterval(() => {
      if (ref.current >= max) { setPlaying(false); return; }
      onChange(ref.current + 1);
    }, interval);
    return () => clearInterval(id);
  }, [playing, max, onChange, interval]);
  const start = () => { if (value >= max) onChange(0); setPlaying(true); };
  return (
    <View style={s.player}>
      <Pressable style={s.pbtn} onPress={() => { setPlaying(false); onChange(Math.max(0, value - 1)); }}
                 accessibilityRole="button" accessibilityLabel="previous">
        <Text style={s.pbtnText}>◀</Text>
      </Pressable>
      <Pressable style={[s.pbtn, s.pbtnMain]} onPress={() => (playing ? setPlaying(false) : start())}
                 accessibilityRole="button" accessibilityLabel={playing ? 'pause' : 'play'}>
        <Text style={[s.pbtnText, { color: t.accent }]}>{playing ? '❚❚ pause' : '▶ play'}</Text>
      </Pressable>
      <Pressable style={s.pbtn} onPress={() => { setPlaying(false); onChange(Math.min(max, value + 1)); }}
                 accessibilityRole="button" accessibilityLabel="next">
        <Text style={s.pbtnText}>▶</Text>
      </Pressable>
      <Text style={s.pval}>{label} = {value} of {max}</Text>
    </View>
  );
}

/**
 * Agents x tasks. A cell is shaded where the agent may hold the task
 * (rho_i <= alpha_j), filled where it does in the assignment, and a collapsed
 * agent's row is struck through.
 */
export function EligibilityGrid({ matrix, rho, alpha, assignment, collapsed = [] }) {
  const { t } = useTheme();
  const s = styles(t);
  if (!matrix) return null;
  const gone = new Set(collapsed);
  return (
    <View>
      <View style={s.gridRow}>
        <Text style={[s.gridHead, { width: 92 }]}>agent · ρ (m)</Text>
        {alpha.map((a, j) => (
          // eslint-disable-next-line react/no-array-index-key
          <Text key={j} style={s.gridHead}>{`T${j}\nα ${fmt(a)}`}</Text>
        ))}
      </View>
      {matrix.map((row, i) => (
        // eslint-disable-next-line react/no-array-index-key
        <View key={i} style={[s.gridRow, gone.has(i) && { opacity: 0.35 }]}>
          <Text style={[s.gridLabel, gone.has(i) && s.strike]}>
            {`A${i} · ${fmt(rho[i])}`}{gone.has(i) ? '  ✕' : ''}
          </Text>
          {row.map((ok, j) => {
            const held = !gone.has(i) && assignment?.[i] === j;
            return (
              // eslint-disable-next-line react/no-array-index-key
              <View key={j} style={[s.cellBox,
                ok && !gone.has(i) ? { backgroundColor: `${t.ok}33` } : null,
                held ? { backgroundColor: t.accent, borderColor: t.accent } : null]}>
                <Text style={[s.cellText, held && { color: t.bg }]}>
                  {held ? '●' : ok ? '' : '·'}
                </Text>
              </View>
            );
          })}
        </View>
      ))}
      <Text style={s.hint}>
        shaded: eligible (ρ_i ≤ α_j) · ● held in the assignment · ✕ certificate collapsed
      </Text>
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  step: {
    flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 7,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  stepNo: {
    width: 20, height: 20, borderRadius: 10, borderWidth: 1, borderColor: t.accent,
    alignItems: 'center', justifyContent: 'center', marginRight: 9, marginTop: 1,
  },
  stepNoText: { color: t.accent, fontSize: 10, fontWeight: '800' },
  stepTitle: { color: t.text, fontSize: 11.5, fontWeight: '700' },
  stepExpr: { color: t.muted, fontSize: 10.5, fontFamily: fonts.mono, marginTop: 2, lineHeight: 15 },
  stepVal: {
    color: t.text, fontSize: 12, fontWeight: '800', fontFamily: fonts.mono,
    marginLeft: 10, minWidth: 90, textAlign: 'right',
  },
  label: {
    color: t.muted, fontSize: 9.5, fontWeight: '700', letterSpacing: 0.5,
    textTransform: 'uppercase', marginBottom: 4, marginTop: 6,
  },
  hint: { color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 6 },
  row: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -4 },
  cell: { flexGrow: 1, flexBasis: 120, paddingHorizontal: 4 },
  player: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', marginVertical: 8 },
  pbtn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 10, paddingVertical: 6, marginRight: 6,
  },
  pbtnMain: { borderColor: t.accent },
  pbtnText: { color: t.text, fontSize: 11, fontWeight: '700' },
  pval: { color: t.muted, fontSize: 11, fontFamily: fonts.mono, marginLeft: 4 },
  gridRow: { flexDirection: 'row', alignItems: 'center' },
  gridHead: {
    width: 44, color: t.muted, fontSize: 9, fontFamily: fonts.mono, textAlign: 'center',
    marginBottom: 3,
  },
  gridLabel: { width: 92, color: t.text, fontSize: 10, fontFamily: fonts.mono },
  strike: { textDecorationLine: 'line-through' },
  cellBox: {
    width: 40, height: 22, margin: 2, borderRadius: 4, borderWidth: 1, borderColor: t.border,
    alignItems: 'center', justifyContent: 'center',
  },
  cellText: { color: t.muted, fontSize: 11, fontWeight: '800' },
});
