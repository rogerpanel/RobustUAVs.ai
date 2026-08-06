import React, { useCallback, useState } from 'react';
import {
  View, Text, Pressable, StyleSheet, Modal, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme, fonts } from '../theme';
import { useLayout } from './useLayout';
import LeftRail from './LeftRail';
import RightRail from './RightRail';
import { DEFAULT_ROUTE, ROUTES, TAB_KEYS, routeMeta } from './nav';

import MilestonesScreen from '../screens/MilestonesScreen';
import CoverScreen from '../screens/CoverScreen';
import OverviewScreen from '../screens/OverviewScreen';
import CompositionScreen from '../screens/CompositionScreen';
import RunsScreen from '../screens/RunsScreen';
import ModelsScreen from '../screens/ModelsScreen';
import CopilotScreen from '../screens/CopilotScreen';

import UAVMonitorScreen from '../screens/uav/UAVMonitorScreen';
import SwarmGraphScreen from '../screens/uav/SwarmGraphScreen';
import FleetDemoScreen from '../screens/uav/FleetDemoScreen';
import GNSSSpoofScreen from '../screens/uav/GNSSSpoofScreen';
import CertificationScreen from '../screens/uav/CertificationScreen';
import MissionPlanScreen from '../screens/uav/MissionPlanScreen';
import PerceptionScreen from '../screens/uav/PerceptionScreen';
import DossierScreen from '../screens/uav/DossierScreen';

const SCREENS = {
  Milestones: MilestonesScreen,
  Cover: CoverScreen,
  Overview: OverviewScreen,
  Composition: CompositionScreen,
  Runs: RunsScreen,
  Registry: ModelsScreen,
  Copilot: CopilotScreen,
  // UAV / Aerial Defense -- the Chapter 6 operator surface.
  UAVMonitor: UAVMonitorScreen,
  SwarmGraph: SwarmGraphScreen,
  FleetDemo: FleetDemoScreen,
  GNSSSpoof: GNSSSpoofScreen,
  Certification: CertificationScreen,
  MissionPlan: MissionPlanScreen,
  Perception: PerceptionScreen,
  Dossier: DossierScreen,
};

/**
 * Three-column responsive shell: left rail, centre, right rail -- collapsing to
 * centre-plus-bottom-tabs on a phone, with both rails reachable as overlays.
 *
 * Routing is a single piece of state rather than a navigator. That is a
 * deliberate trade: react-navigation's drawer needs `gesture-handler` and
 * `reanimated`, both of which are the usual suspects when an Expo web export
 * breaks, and this app has exactly one level of navigation with no history to
 * manage. Screens still receive a `navigation` prop shaped like the real one,
 * so nothing had to be rewritten to fit -- and swapping a real navigator back
 * in later would touch only this file.
 */
export default function Shell() {
  const { t } = useTheme();
  const L = useLayout();
  const s = styles(t, L);

  const [route, setRoute] = useState(DEFAULT_ROUTE);
  const [menuOpen, setMenuOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);

  const navigate = useCallback((key) => {
    if (SCREENS[key]) setRoute(key);
    setMenuOpen(false);
  }, []);

  // Shaped like react-navigation's prop so screens are agnostic to which one
  // is driving them.
  const navigation = { navigate, goBack: () => setRoute(DEFAULT_ROUTE) };

  const Screen = SCREENS[route] ?? MilestonesScreen;
  const meta = routeMeta(route);

  return (
    <SafeAreaView style={s.root} edges={['top', 'left', 'right']}>
      <View style={s.columns}>

        {L.showLeftRail ? (
          <LeftRail route={route} onNavigate={navigate} />
        ) : null}

        <View style={s.centre}>
          {/* The compact header carries what the rails otherwise would: the
              wordmark, the menu, and the context panel. */}
          {L.compact ? (
            <View style={s.topbar}>
              <Pressable onPress={() => setMenuOpen(true)} style={s.iconBtn}
                         accessibilityRole="button" accessibilityLabel="Open menu">
                <Text style={s.icon}>☰</Text>
              </Pressable>
              <Text style={s.topTitle} numberOfLines={1}>{meta.title}</Text>
              <Pressable onPress={() => setInfoOpen(true)} style={s.iconBtn}
                         accessibilityRole="button" accessibilityLabel="Deployment and artifact">
                <Text style={s.icon}>ⓘ</Text>
              </Pressable>
            </View>
          ) : null}

          {/* Medium screens have the left rail but not the right one, so the
              context panel needs a way in. */}
          {L.medium ? (
            <View style={s.mediumBar}>
              <Text style={s.mediumTitle}>{meta.title}</Text>
              <Pressable onPress={() => setInfoOpen(true)} style={s.mediumBtn}
                         accessibilityRole="button">
                <Text style={s.mediumBtnText}>ⓘ  status &amp; artifact</Text>
              </Pressable>
            </View>
          ) : null}

          <View style={s.centreBody}>
            <View style={[s.centreInner, { maxWidth: L.contentMax }]}>
              <Screen navigation={navigation} />
            </View>
          </View>

          {L.showTabs ? (
            <BottomTabs route={route} onNavigate={navigate}
                        onMore={() => setMenuOpen(true)} />
          ) : null}
        </View>

        {L.showRightRail ? <RightRail /> : null}
      </View>

      {/* Overlays. `Modal` is the one primitive that behaves identically on
          web and native here, so the drawer needs no platform branch. */}
      <Overlay visible={menuOpen} onClose={() => setMenuOpen(false)} t={t} side="left">
        <LeftRail route={route} onNavigate={navigate} compact
                  onDismiss={() => setMenuOpen(false)} />
      </Overlay>

      <Overlay visible={infoOpen} onClose={() => setInfoOpen(false)} t={t} side="right">
        <RightRail compact onDismiss={() => setInfoOpen(false)} />
      </Overlay>
    </SafeAreaView>
  );
}

function Overlay({ visible, onClose, t, side, children }) {
  const s = styles(t, { compact: true });
  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={onClose}>
      <View style={s.scrim}>
        <Pressable style={s.scrimFill} onPress={onClose} accessibilityLabel="Dismiss" />
        <View style={[s.sheet, side === 'right' ? s.sheetRight : s.sheetLeft]}>
          {children}
        </View>
      </View>
    </Modal>
  );
}

/**
 * Bottom tabs. Four routes plus "More", sized for a thumb: the row is 58 px
 * tall and each target spans a full fifth of the width, which clears the 44 px
 * minimum on every phone we care about without crowding the labels.
 */
function BottomTabs({ route, onNavigate, onMore }) {
  const { t } = useTheme();
  const s = styles(t, { compact: true });
  const tabs = TAB_KEYS.map((k) => ROUTES.find((r) => r.key === k)).filter(Boolean);

  return (
    <SafeAreaView edges={['bottom']} style={s.tabWrap}>
      <View style={s.tabs}>
        {tabs.map((it) => {
          const on = it.key === route;
          return (
            <Pressable key={it.key} onPress={() => onNavigate(it.key)}
                       style={s.tab} accessibilityRole="button"
                       accessibilityState={{ selected: on }}>
              <Text style={[s.tabGlyph, on && { color: t.accent }]}>{it.glyph}</Text>
              <Text style={[s.tabLabel, on && { color: t.accent }]} numberOfLines={1}>
                {it.title}
              </Text>
            </Pressable>
          );
        })}
        <Pressable onPress={onMore} style={s.tab} accessibilityRole="button"
                   accessibilityLabel="More screens">
          <Text style={s.tabGlyph}>☰</Text>
          <Text style={s.tabLabel}>More</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = (t, L) => StyleSheet.create({
  root: { flex: 1, backgroundColor: t.bg },
  columns: { flex: 1, flexDirection: 'row' },
  centre: { flex: 1, backgroundColor: t.bg },
  centreBody: { flex: 1, alignItems: 'center' },
  centreInner: { flex: 1, width: '100%' },

  topbar: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 6, paddingVertical: 6,
    borderBottomWidth: 1, borderBottomColor: t.border,
    backgroundColor: t.panel,
  },
  iconBtn: {
    width: 46, height: 46, alignItems: 'center', justifyContent: 'center',
  },
  icon: { color: t.text, fontSize: 19 },
  topTitle: {
    flex: 1, color: t.text, fontSize: 15, fontWeight: '700',
    textAlign: 'center', fontFamily: fonts.display,
  },

  mediumBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: t.border,
  },
  mediumTitle: { color: t.text, fontSize: 14, fontWeight: '700', fontFamily: fonts.display },
  mediumBtn: {
    borderWidth: 1, borderColor: t.border, borderRadius: 7,
    paddingHorizontal: 10, paddingVertical: 6,
  },
  mediumBtnText: { color: t.muted, fontSize: 11, fontWeight: '600' },

  scrim: { flex: 1, flexDirection: 'row', backgroundColor: '#00000099' },
  scrimFill: { flex: 1 },
  sheet: {
    width: '86%', maxWidth: 340, backgroundColor: t.panel,
    borderColor: t.border,
  },
  sheetLeft: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRightWidth: 1 },
  sheetRight: { position: 'absolute', right: 0, top: 0, bottom: 0, borderLeftWidth: 1 },

  tabWrap: { backgroundColor: t.panel, borderTopWidth: 1, borderTopColor: t.border },
  tabs: { flexDirection: 'row', height: 58 },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  tabGlyph: { color: t.muted, fontSize: 16 },
  tabLabel: { color: t.muted, fontSize: 9.5, marginTop: 2, fontWeight: '600' },
});
