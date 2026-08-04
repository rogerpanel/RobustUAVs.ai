import React, { useState } from 'react';
import { View, Text, TextInput, ScrollView, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { api } from '../api/client';
import { theme } from '../theme';
import Card from '../components/Card';
import Chip from '../components/Chip';

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
  const [q, setQ] = useState('');
  const [turns, setTurns] = useState([]);
  const [busy, setBusy] = useState(false);

  const ask = async (question) => {
    const text = (question ?? q).trim();
    if (!text || busy) return;
    setBusy(true); setQ('');
    try {
      const r = await api.ask(text);
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
        <Text style={styles.h1}>Copilot</Text>
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
              <Text style={[styles.a, t.error && { color: theme.danger }]}>{t.answer}</Text>
              <View style={styles.chips}>
                {t.provider ? (
                  <Chip label={t.synthetic ? `${t.provider} (fallback)` : t.provider}
                        color={t.synthetic ? theme.bridge : theme.ok} />
                ) : null}
                {(t.tools_used || []).map((x) => <Chip key={x} label={x} color={theme.network} />)}
              </View>
            </Card>
          </View>
        ))}
        {busy ? <ActivityIndicator color={theme.accent} /> : null}
      </ScrollView>

      <View style={styles.bar}>
        <TextInput
          style={styles.input} value={q} onChangeText={setQ}
          placeholder="Ask a question…" placeholderTextColor={theme.muted}
          onSubmitEditing={() => ask()} returnKeyType="send"
        />
        <Pressable onPress={() => ask()} style={styles.send}>
          <Text style={styles.sendText}>Ask</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.bg },
  content: { padding: 16, paddingBottom: 24 },
  h1: { color: theme.text, fontSize: 24, fontWeight: '800', marginBottom: 12 },
  sugg: { borderWidth: 1, borderColor: theme.border, borderRadius: 8, padding: 10, marginTop: 8 },
  suggText: { color: theme.accent, fontSize: 13 },
  q: { color: theme.muted, fontSize: 13, fontWeight: '700', marginBottom: 6, marginTop: 6 },
  a: { color: theme.text, fontSize: 13, lineHeight: 20 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  bar: { flexDirection: 'row', padding: 12, borderTopWidth: 1, borderTopColor: theme.border },
  input: {
    flex: 1, backgroundColor: theme.card, borderWidth: 1, borderColor: theme.border,
    borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: theme.text, fontSize: 14,
  },
  send: {
    marginLeft: 8, paddingHorizontal: 16, justifyContent: 'center',
    backgroundColor: theme.accent, borderRadius: 8,
  },
  sendText: { color: theme.bg, fontWeight: '800' },
});
