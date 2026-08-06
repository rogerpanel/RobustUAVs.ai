import React, { useEffect, useState } from 'react';
import {
  View, Text, Pressable, StyleSheet, TextInput, Modal,
} from 'react-native';
import { api } from '../api/client';
import { useTheme, fonts } from '../theme';

/**
 * Provider selector and key entry, in the page's top-left corner.
 *
 * Anthropic is the default: the deployment carries a key for it, so a visitor
 * gets narrated answers without supplying anything. That shared allowance is
 * metered per session, and supplying your own key bypasses the meter.
 *
 * A key typed here is held in component state for the life of the page and sent
 * with each request. It is deliberately NOT written to localStorage: persisting
 * someone else's provider credential in a browser store, on a machine that may
 * be a shared conference laptop, is not a trade this artifact should make for
 * the convenience of not retyping it.
 */
const PROVIDERS = [
  { id: 'anthropic', label: 'Claude', model: 'claude-sonnet-5', placeholder: 'sk-ant-…' },
  { id: 'openai', label: 'OpenAI', model: 'gpt-4o', placeholder: 'sk-…' },
  { id: 'gemini', label: 'Gemini', model: 'gemini-2.0-flash', placeholder: 'AIza…' },
  { id: 'deepseek', label: 'DeepSeek', model: 'deepseek-chat', placeholder: 'sk-…' },
];

export default function ProviderMenu({ provider, apiKey, onChange }) {
  const { t } = useTheme();
  const s = styles(t);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(apiKey ?? '');
  const [status, setStatus] = useState(null);
  const [rate, setRate] = useState(null);

  useEffect(() => {
    api.health()
      .then((h) => { setStatus(h.llm ?? h.providers ?? null); setRate(h.rate?.llm ?? null); })
      .catch(() => {});
  }, [open]);

  const active = PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0];
  const usingOwn = !!apiKey;

  return (
    <>
      <Pressable onPress={() => setOpen(true)} style={s.trigger}
                 accessibilityRole="button" accessibilityLabel="Choose LLM provider">
        <Text style={s.triggerText}>
          {active.label}{usingOwn ? ' · your key' : ''}  ▾
        </Text>
      </Pressable>

      <Modal visible={open} transparent animationType="fade"
             onRequestClose={() => setOpen(false)}>
        <Pressable style={s.scrim} onPress={() => setOpen(false)} />
        <View style={s.sheet}>
          <Text style={s.title}>Language model</Text>
          <Text style={s.body}>
            Claude is the default and this deployment supplies the key, so the
            copilot works with nothing to configure. Supply your own key to use a
            different provider or to bypass the shared hourly allowance.
          </Text>

          {PROVIDERS.map((p) => {
            const on = p.id === active.id;
            const configured = Array.isArray(status)
              ? status.find((x) => x.name === p.id)?.configured
              : undefined;
            return (
              <Pressable key={p.id} onPress={() => onChange({ provider: p.id, apiKey })}
                         style={[s.row, on && s.rowOn]}>
                <View style={[s.radio, on && { borderColor: t.accent }]}>
                  {on ? <View style={s.radioDot} /> : null}
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[s.name, on && { color: t.text }]}>
                    {p.label}{p.id === 'anthropic' ? '  · default' : ''}
                  </Text>
                  <Text style={s.model}>{p.model}</Text>
                </View>
                {configured ? <Text style={s.ok}>server key</Text> : null}
              </Pressable>
            );
          })}

          <Text style={s.label}>Your API key (optional)</Text>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder={active.placeholder}
            placeholderTextColor={t.muted}
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            style={s.input}
          />
          <Text style={s.note}>
            Sent with each request over TLS and used for that request only. Never
            written to storage, never logged, never returned by the API.
          </Text>

          {rate ? (
            <Text style={s.note}>
              Shared allowance: {rate.used} of {rate.limit} answers used this hour.
            </Text>
          ) : null}

          <View style={s.actions}>
            <Pressable onPress={() => { setDraft(''); onChange({ provider: 'anthropic', apiKey: null }); setOpen(false); }}
                       style={s.btn}>
              <Text style={s.btnText}>use default</Text>
            </Pressable>
            <Pressable onPress={() => { onChange({ provider: active.id, apiKey: draft.trim() || null }); setOpen(false); }}
                       style={[s.btn, s.btnPrimary]}>
              <Text style={[s.btnText, { color: t.accent }]}>apply</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = (t) => StyleSheet.create({
  trigger: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 10, paddingVertical: 6, alignSelf: 'flex-start',
  },
  triggerText: { color: t.muted, fontSize: 11, fontWeight: '700' },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: '#00000099' },
  sheet: {
    position: 'absolute', top: 60, left: 16, right: 16, maxWidth: 420,
    backgroundColor: t.panel, borderWidth: 1, borderColor: t.border,
    borderRadius: 11, padding: 15,
  },
  title: { color: t.text, fontSize: 14, fontWeight: '800', fontFamily: fonts.display },
  body: { color: t.muted, fontSize: 11, lineHeight: 16.5, marginTop: 5, marginBottom: 10 },
  row: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 8,
    paddingHorizontal: 8, borderRadius: 7, marginBottom: 3,
  },
  rowOn: { backgroundColor: `${t.accent}14` },
  radio: {
    width: 14, height: 14, borderRadius: 7, borderWidth: 1, borderColor: t.border,
    marginRight: 9, alignItems: 'center', justifyContent: 'center',
  },
  radioDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: t.accent },
  name: { color: t.muted, fontSize: 12, fontWeight: '700' },
  model: { color: t.muted, fontSize: 9.5, fontFamily: fonts.mono, opacity: 0.8 },
  ok: { color: t.ok, fontSize: 9, fontWeight: '700' },
  label: {
    color: t.muted, fontSize: 9, fontWeight: '800', letterSpacing: 0.8,
    textTransform: 'uppercase', marginTop: 10, marginBottom: 5,
  },
  input: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 10, paddingVertical: 8, color: t.text,
    backgroundColor: t.bg, fontSize: 12, fontFamily: fonts.mono,
  },
  note: { color: t.muted, fontSize: 9.5, lineHeight: 14.5, marginTop: 6 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 12 },
  btn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 14, paddingVertical: 9, marginLeft: 8,
  },
  btnPrimary: { borderColor: t.accent, backgroundColor: `${t.accent}18` },
  btnText: { color: t.muted, fontSize: 11.5, fontWeight: '700' },
});
