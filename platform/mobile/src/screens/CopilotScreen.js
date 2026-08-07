import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, ScrollView, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { api } from '../api/client';
import { useTheme } from '../theme';
import Card from '../components/Card';
import Chip from '../components/Chip';
import { subscribeContext, clearContext } from '../state/context';
import ProviderMenu from '../components/ProviderMenu';

const SUGGESTIONS = [
  'Is theta = 0.25 s inside the certified window?',
  'What is the measured delay-to-position rate?',
  'How much of the benchmark is real measurement?',
  'Does the composed guarantee dominate the baselines?',
];

/** The copilot. Every answer shows which tools ran, which files they read, and
 *  whether a real provider or the deterministic fallback produced the prose --
 *  so a viewer can always tell an assertion from a citation. */
export default function CopilotScreen() {
  const { t } = useTheme();
  const styles = makeStyles(t);
  const [q, setQ] = useState('');
  const [turns, setTurns] = useState([]);
  const [busy, setBusy] = useState(false);
  // Chips built from what the user has actually just done elsewhere in the
  // app. A chip is not a canned prompt: it carries the numbers that screen
  // produced, so the copilot answers about their session rather than in
  // general.
  const [ctx, setCtx] = useState([]);
  useEffect(() => subscribeContext(setCtx), []);
  // Provider choice and an optional caller key. Held here for the life of the
  // page and never persisted -- see components/ProviderMenu.js.
  const [llm, setLlm] = useState({ provider: 'anthropic', apiKey: null });

  const ask = async (question) => {
    const text = (question ?? q).trim();
    if (!text || busy) return;
    setBusy(true); setQ('');
    try {
      const r = await api.ask(text, llm.provider, llm.apiKey);
      setTurns((t) => [...t, r]);
    } catch (e) {
      setTurns((t) => [...t, { question: text, answer: `Error: ${e.message}`, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.topbar}>
          <ProviderMenu provider={llm.provider} apiKey={llm.apiKey} onChange={setLlm} />
        </View>
        <Text style={styles.h1}>Copilot</Text>
        {ctx.length > 0 ? (
          <Card title="Your results"
                subtitle="One chip per page you have run something on. Each carries that page's actual numbers — tap to ask about them.">
            <View style={styles.chips}>
              {ctx.map((c) => (
                <Pressable key={`${c.routeKey}-${c.label}`} onPress={() => ask(c.question)}
                           style={styles.ctxChip} accessibilityRole="button">
                  <Text style={styles.ctxChipText}>{c.label}</Text>
                </Pressable>
              ))}
            </View>
            <Pressable onPress={clearContext} style={styles.clearCtx}>
              <Text style={styles.clearCtxText}>clear context</Text>
            </Pressable>
          </Card>
        ) : null}

        {turns.length === 0 ? (
          <Card title="Ask about the benchmark or the guarantee"
                subtitle="Answers are assembled from the committed result files and cite them.">
            {SUGGESTIONS.map((s) => (
              <Pressable key={s} onPress={() => ask(s)} style={styles.sugg}>
                <Text style={styles.suggText}>{s}</Text>
              </Pressable>
            ))}
          </Card>
        ) : null}

        {turns.map((t, i) => (
          <View key={i}>
            <Text style={styles.q}>{t.question}</Text>
            <Card source={t.sources?.join(', ')}>
              <Text style={[styles.a, t.error && { color: t.danger }]}>{t.answer}</Text>
              <View style={styles.chips}>
                {t.provider ? (
                  <Chip label={t.synthetic ? `${t.provider} (fallback)` : t.provider}
                        color={t.synthetic ? t.bridge : t.ok} />
                ) : null}
                {(t.tools_used || []).map((x) => <Chip key={x} label={x} color={t.network} />)}
              </View>
            </Card>
          </View>
        ))}
        {busy ? <ActivityIndicator color={t.accent} /> : null}
      </ScrollView>

      <View style={styles.bar}>
        <TextInput
          style={styles.input} value={q} onChangeText={setQ}
          placeholder="Ask a question…" placeholderTextColor={t.muted}
          onSubmitEditing={() => ask()} returnKeyType="send"
        />
        <Pressable onPress={() => ask()} style={styles.send}>
          <Text style={styles.sendText}>Ask</Text>
        </Pressable>
      </View>
    </View>
  );
}

const makeStyles = (t) => StyleSheet.create({
  topbar: { flexDirection: 'row', marginBottom: 10 },
  chips: { flexDirection: 'row', flexWrap: 'wrap' },
  ctxChip: {
    borderWidth: 1, borderColor: t.accent, backgroundColor: `${t.accent}14`,
    borderRadius: 7, paddingHorizontal: 10, paddingVertical: 7,
    marginRight: 6, marginBottom: 6,
  },
  ctxChipText: { color: t.accent, fontSize: 11, fontWeight: '700' },
  clearCtx: { alignSelf: 'flex-start', paddingVertical: 6 },
  clearCtxText: { color: t.muted, fontSize: 10, fontWeight: '600' },
  screen: { flex: 1, backgroundColor: t.bg },
  content: { padding: 16, paddingBottom: 24 },
  h1: { color: t.text, fontSize: 24, fontWeight: '800', marginBottom: 12 },
  sugg: { borderWidth: 1, borderColor: t.border, borderRadius: 8, padding: 10, marginTop: 8 },
  suggText: { color: t.accent, fontSize: 13 },
  q: { color: t.muted, fontSize: 13, fontWeight: '700', marginBottom: 6, marginTop: 6 },
  a: { color: t.text, fontSize: 13, lineHeight: 20 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  bar: { flexDirection: 'row', padding: 12, borderTopWidth: 1, borderTopColor: t.border },
  input: {
    flex: 1, backgroundColor: t.card, borderWidth: 1, borderColor: t.border,
    borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: t.text, fontSize: 14,
  },
  send: {
    marginLeft: 8, paddingHorizontal: 16, justifyContent: 'center',
    backgroundColor: t.accent, borderRadius: 8,
  },
  sendText: { color: t.bg, fontWeight: '800' },
});
