import React, { useState } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useTheme, fonts } from '../theme';

/**
 * The numbered "how to use this page" note, dismissible per page.
 *
 * Rendered by the shell from the route's own metadata rather than by each
 * screen, so a page cannot ship without one and the wording lives beside the
 * navigation entry it belongs to.
 *
 * Dismissal is remembered for the session and, on the web, across reloads. A
 * presenter who dismissed the note during rehearsal should not have it reappear
 * on stage; a first-time visitor should still see it. `localStorage` is
 * accessed defensively because it does not exist on native and can throw in a
 * private-mode browser.
 */
const KEY = 'robustuavs.howto.dismissed';

function loadDismissed() {
  try {
    if (typeof localStorage === 'undefined') return {};
    return JSON.parse(localStorage.getItem(KEY) || '{}');
  } catch { return {}; }
}
function saveDismissed(map) {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, JSON.stringify(map));
  } catch { /* private mode, or native: session-only is fine */ }
}

export default function HowTo({ routeKey, title, steps, tip }) {
  const { t } = useTheme();
  const s = styles(t);
  const [dismissed, setDismissed] = useState(() => loadDismissed());

  if (!steps || steps.length === 0) return null;

  const isHidden = !!dismissed[routeKey];

  const hide = () => {
    const next = { ...dismissed, [routeKey]: true };
    setDismissed(next); saveDismissed(next);
  };
  const show = () => {
    const next = { ...dismissed }; delete next[routeKey];
    setDismissed(next); saveDismissed(next);
  };

  if (isHidden) {
    return (
      <Pressable onPress={show} style={s.reopen} accessibilityRole="button">
        <Text style={s.reopenText}>ⓘ  how to use this page</Text>
      </Pressable>
    );
  }

  return (
    <View style={s.box}>
      <View style={s.head}>
        <Text style={s.title}>ⓘ  How to use {title}</Text>
        <Pressable onPress={hide} style={s.close}
                   accessibilityRole="button" accessibilityLabel="Hide this guide">
          <Text style={s.closeText}>✕</Text>
        </Pressable>
      </View>
      {steps.map((step, i) => (
        <View key={step} style={s.step}>
          <Text style={s.num}>{i + 1}</Text>
          <Text style={s.stepText}>{step}</Text>
        </View>
      ))}
      {tip ? <Text style={s.tip}>{tip}</Text> : null}
    </View>
  );
}

const styles = (t) => StyleSheet.create({
  box: {
    borderWidth: 1, borderColor: `${t.network}55`,
    backgroundColor: `${t.network}12`,
    borderRadius: 9, padding: 12, marginBottom: 14,
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { color: t.network, fontSize: 12.5, fontWeight: '800', flex: 1 },
  close: { width: 30, height: 30, alignItems: 'center', justifyContent: 'center' },
  closeText: { color: t.muted, fontSize: 14 },
  step: { flexDirection: 'row', marginTop: 7 },
  num: {
    color: t.network, fontSize: 10, fontWeight: '800', width: 16,
    fontFamily: fonts.mono, paddingTop: 1.5,
  },
  stepText: { color: t.text, fontSize: 11.5, lineHeight: 17, flex: 1 },
  tip: {
    color: t.network, fontSize: 11, lineHeight: 16.5, marginTop: 9,
    fontStyle: 'italic',
  },
  reopen: {
    alignSelf: 'flex-start', borderWidth: 1, borderColor: t.border,
    borderRadius: 7, paddingHorizontal: 10, paddingVertical: 6, marginBottom: 12,
  },
  reopenText: { color: t.muted, fontSize: 10.5, fontWeight: '600' },
});
