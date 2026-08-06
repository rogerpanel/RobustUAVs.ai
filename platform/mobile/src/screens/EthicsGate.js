import React, { useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Pressable, Linking, useWindowDimensions,
} from 'react-native';
import { useTheme, fonts } from '../theme';

/**
 * Ethical-use notice, shown once before the application is reachable.
 *
 * This is a real gate, not a formality: the artifact publishes attack traces, a
 * detector operating curve and a fleet simulator, and the combination is
 * dual-use. Anyone can read what is expected of them before they see any of it.
 *
 * Acceptance is recorded locally with the version string. Bumping ACCEPT_VERSION
 * re-prompts everyone, which is what should happen when the terms change --
 * a silently-updated policy that people are still deemed to have accepted is
 * worse than no policy.
 */
const ACCEPT_VERSION = '2026-08-06';
const KEY = 'robustuavs.ethics.accepted';

export function hasAccepted() {
  try {
    if (typeof localStorage === 'undefined') return false;
    return localStorage.getItem(KEY) === ACCEPT_VERSION;
  } catch { return false; }
}

function record() {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, ACCEPT_VERSION);
  } catch { /* private mode: the gate reappears next visit, which is fine */ }
}

const SECTIONS = [
  {
    icon: '◆', title: '1. Permitted use',
    lead: 'This platform is published for research, education and defensive '
        + 'evaluation. Permitted uses include:',
    items: [
      'Reproducing the published results and auditing the committed artifact.',
      'Evaluating intrusion detectors and navigation defences against the released benchmark.',
      'Academic study, teaching, and peer review of the accompanying manuscript.',
      'Assessing systems you own, or are explicitly authorised in writing to assess.',
    ],
  },
  {
    icon: '⚠', title: '2. Prohibited use',
    lead: 'The following are prohibited without exception:',
    items: [
      'Interfering with any aircraft, GNSS receiver or radio link you do not own or are not authorised to test.',
      'Transmitting jamming or spoofing signals against live navigation systems. In most jurisdictions this is a criminal offence, and it endangers aircraft carrying people.',
      'Applying these methods to weapons systems, targeting, or any use intended to cause physical harm.',
      'Redistributing attack methodologies, model weights or generated payloads to unauthorised parties.',
      'Any activity violating applicable local, national or international law.',
    ],
  },
  {
    icon: '§', title: '3. Regulatory and standards context',
    lead: 'Users are expected to operate consistently with the frameworks this '
        + 'work is evaluated against:',
    items: [
      'ICAO Annex 2 and national UAS regulations — airspace access and operator responsibility.',
      'JARUS SORA v2.5 — operational volume, contingency volume and ground risk buffer.',
      'DO-326A / ED-202A — airworthiness security process, and the 0.90 completion floor used here.',
      'EU AI Act (2024/1689) — risk-based regulation of AI systems.',
      'ISO/IEC 27001:2022 and ISO/IEC 23894:2023 — information security and AI risk management.',
      'GDPR (2016/679) — where any uploaded data contains personal information.',
      'MITRE ATT&CK / ATLAS — adversarial threat modelling vocabulary.',
    ],
  },
  {
    icon: '◇', title: '4. Responsible research principles',
    items: [
      'Transparency — every figure names the committed file it was computed from, and results that weaken our own claims are shown with equal weight.',
      'Honest reporting — pages that cannot compute a quantity say so rather than substituting a plausible one.',
      'Accountability — you bear full responsibility for how you apply these tools, results and artifacts.',
      'Privacy — uploaded files are parsed in flight and discarded; nothing is retained. Do not upload data you are not entitled to process.',
      'Safety first — simulation is not a substitute for a risk assessment. Nothing here certifies a real aircraft.',
    ],
  },
];

export default function EthicsGate({ onAccept }) {
  const { t } = useTheme();
  const { height } = useWindowDimensions();
  const s = styles(t);
  const [readTerms, setReadTerms] = useState(false);
  const [reportAbuse, setReportAbuse] = useState(false);

  const ready = readTerms && reportAbuse;

  const accept = () => {
    if (!ready) return;
    record();
    onAccept();
  };

  return (
    <View style={s.backdrop}>
      <View style={s.card}>
        <View style={s.header}>
          <Text style={s.wordmark}>
            RobustUAVs<Text style={{ color: t.accent }}>.ai</Text>
          </Text>
          <Text style={s.title}>⚖  Ethical Use Guidance &amp; Caution</Text>
        </View>

        <ScrollView style={[s.body, { maxHeight: Math.max(220, height * 0.5) }]}
                    contentContainerStyle={s.bodyInner}>
          <Text style={s.preamble}>
            This artifact accompanies a peer-reviewed submission on UAV security.
            It publishes attack traces, a detector operating curve, and a
            simulator that models how network attacks degrade flight. That
            combination is dual-use. Read this before continuing.
          </Text>

          {SECTIONS.map((sec) => (
            <View key={sec.title} style={s.section}>
              <Text style={s.sectionTitle}>{sec.icon}  {sec.title}</Text>
              {sec.lead ? <Text style={s.lead}>{sec.lead}</Text> : null}
              {sec.items.map((it) => (
                <View key={it} style={s.bullet}>
                  <Text style={s.dot}>•</Text>
                  <Text style={s.bulletText}>{it}</Text>
                </View>
              ))}
            </View>
          ))}

          <Text style={s.footnote}>
            No account is required and no personal data is collected. A random
            session identifier is stored in your browser so your own experiments
            stay separate from other visitors'; it identifies nothing about you
            and can be cleared at any time.
          </Text>
        </ScrollView>

        <View style={s.consent}>
          <Check t={t} on={readTerms} onToggle={() => setReadTerms((v) => !v)}
                 label="I have read and understand the Ethical Use Guidance & Caution above, and agree to abide by all stated terms, prohibitions and regulatory requirements." />
          <Check t={t} on={reportAbuse} onToggle={() => setReportAbuse((v) => !v)}
                 label="I agree to report any abuse or policy violation I encounter to the maintainer." />

          <Pressable onPress={accept} disabled={!ready}
                     style={[s.agree, !ready && s.agreeOff]}
                     accessibilityRole="button"
                     accessibilityState={{ disabled: !ready }}>
            <Text style={[s.agreeText, !ready && { color: t.muted }]}>
              ⚑  I Agree
            </Text>
          </Pressable>
          {!ready ? (
            <Text style={s.hint}>Both boxes must be ticked to continue.</Text>
          ) : null}
        </View>
      </View>
    </View>
  );
}

function Check({ t, on, onToggle, label }) {
  const s = styles(t);
  return (
    <Pressable onPress={onToggle} style={s.check} accessibilityRole="checkbox"
               accessibilityState={{ checked: on }}>
      <View style={[s.box, on && { borderColor: t.accent, backgroundColor: `${t.accent}33` }]}>
        {on ? <Text style={s.tick}>✓</Text> : null}
      </View>
      <Text style={s.checkLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = (t) => StyleSheet.create({
  backdrop: {
    flex: 1, backgroundColor: t.bg, alignItems: 'center', justifyContent: 'center',
    padding: 16,
  },
  card: {
    width: '100%', maxWidth: 660, backgroundColor: t.panel,
    borderWidth: 1, borderColor: t.border, borderRadius: 12, overflow: 'hidden',
  },
  header: { alignItems: 'center', paddingVertical: 16, paddingHorizontal: 16 },
  wordmark: {
    color: t.text, fontSize: 20, fontWeight: '800', fontFamily: fonts.display,
    letterSpacing: -0.5,
  },
  title: { color: t.accent, fontSize: 13, fontWeight: '800', marginTop: 6 },
  body: {
    borderTopWidth: 1, borderBottomWidth: 1, borderColor: t.border,
    backgroundColor: t.bg,
  },
  bodyInner: { padding: 16 },
  preamble: { color: t.text, fontSize: 12.5, lineHeight: 19, marginBottom: 14 },
  section: { marginBottom: 14 },
  sectionTitle: { color: t.text, fontSize: 12.5, fontWeight: '800', marginBottom: 5 },
  lead: { color: t.muted, fontSize: 11.5, lineHeight: 17, marginBottom: 5 },
  bullet: { flexDirection: 'row', marginBottom: 4 },
  dot: { color: t.accent, fontSize: 11, width: 14, paddingTop: 1 },
  bulletText: { color: t.muted, fontSize: 11.5, lineHeight: 17, flex: 1 },
  footnote: {
    color: t.muted, fontSize: 10.5, lineHeight: 16, marginTop: 6,
    fontStyle: 'italic',
  },
  consent: { padding: 16 },
  check: { flexDirection: 'row', marginBottom: 10 },
  box: {
    width: 17, height: 17, borderRadius: 4, borderWidth: 1, borderColor: t.border,
    marginRight: 9, alignItems: 'center', justifyContent: 'center', marginTop: 1,
  },
  tick: { color: t.accent, fontSize: 11, fontWeight: '800' },
  checkLabel: { color: t.text, fontSize: 11.5, lineHeight: 17, flex: 1 },
  agree: {
    borderWidth: 1, borderColor: t.accent, backgroundColor: `${t.accent}1F`,
    borderRadius: 8, paddingVertical: 13, alignItems: 'center', marginTop: 6,
  },
  agreeOff: { borderColor: t.border, backgroundColor: 'transparent' },
  agreeText: { color: t.accent, fontSize: 13.5, fontWeight: '800', letterSpacing: 0.5 },
  hint: { color: t.muted, fontSize: 10.5, textAlign: 'center', marginTop: 7 },
});
