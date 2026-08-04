import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';

import OverviewScreen from './src/screens/OverviewScreen';
import ModelsScreen from './src/screens/ModelsScreen';
import CompositionScreen from './src/screens/CompositionScreen';
import CopilotScreen from './src/screens/CopilotScreen';
import { theme } from './src/theme';

const Tab = createBottomTabNavigator();

const navTheme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: theme.bg, card: theme.card,
            border: theme.border, text: theme.text, primary: theme.accent },
};

const icon = (glyph) => ({ color }) => <Text style={{ color, fontSize: 18 }}>{glyph}</Text>;

export default function App() {
  return (
    <NavigationContainer theme={navTheme}>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: theme.accent,
          tabBarInactiveTintColor: theme.muted,
          tabBarStyle: { backgroundColor: theme.card, borderTopColor: theme.border },
        }}>
        <Tab.Screen name="Overview" component={OverviewScreen}
                    options={{ tabBarIcon: icon('◈') }} />
        <Tab.Screen name="Composition" component={CompositionScreen}
                    options={{ tabBarIcon: icon('⟶') }} />
        <Tab.Screen name="Registry" component={ModelsScreen}
                    options={{ tabBarIcon: icon('▤') }} />
        <Tab.Screen name="Copilot" component={CopilotScreen}
                    options={{ tabBarIcon: icon('✦') }} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
